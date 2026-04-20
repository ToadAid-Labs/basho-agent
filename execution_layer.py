"""
Execution Layer - Trading Execution System
Handles trade execution with slippage protection, gas optimization,
transaction queuing, multi-DEX routing, and flash loan integration.
"""

from typing import Dict, List, Tuple, Optional, Union
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import time
import heapq
import hashlib
import json
from decimal import Decimal, getcontext
import asyncio

# Set decimal precision
getcontext().prec = 18

class Network(Enum):
    """Supported blockchain networks"""
    ETHEREUM = "ethereum"
    BSC = "bsc"
    ARBITRUM = "arbitrum"
    OPTIMISM = "optimism"
    POLYGON = "polygon"
    AVALANCHE = "avalanche"


class DEX(Enum):
    """Supported DEX platforms"""
    UNISWAP_V2 = "uniswap_v2"
    UNISWAP_V3 = "uniswap_v3"
    PANCAKESWAP = "pancakeswap"
    SUSHISWAP = "sushiswap"
    SHIBASWAP = "shibaswap"
    QUICKSWAP = "quickswap"


class TransactionStatus(Enum):
    """Transaction status tracking"""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


class ExecutionStrategy(Enum):
    """Execution strategies"""
    BEST_PRICE = "best_price"
    LOWEST_SLIPPAGE = "lowest_slippage"
    FASTEST_GAS = "fastest_gas"
    RISK_AVERSE = "risk_averse"


@dataclass
class Transaction:
    """Represents a queued transaction"""
    tx_id: str
    token_address: str
    amount: float
    dex: DEX
    network: Network
    status: TransactionStatus
    created_at: datetime
    priority: int = 0
    gas_price: Optional[float] = None
    estimated_gas: Optional[float] = None
    slippage: Optional[float] = None
    source_tx_hash: Optional[str] = None
    destination_tx_hash: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class ExecutionResult:
    """Result of trade execution"""
    success: bool
    tx_id: str
    transaction: Optional[Transaction]
    actual_amount: float
    actual_slippage: float
    gas_used: Optional[float]
    cost: Optional[float]
    gas_cost: Optional[float]  # Alias for cost
    message: str
    execution_time: float


@dataclass
class PriceImpact:
    """Price impact calculation"""
    expected_price: float
    actual_price: float
    slippage: float
    impact_percentage: float


@dataclass
class GasEstimate:
    """Gas cost estimation"""
    gas_price: float  # gwei
    gas_limit: int
    gas_used: int
    cost_wei: int
    cost_eth: float
    cost_bsc: float
    cost_arbitrum: float
    cost_polygon: float
    cost_optimism: float


@dataclass
class FlashLoanRequest:
    """Flash loan request parameters"""
    token: str
    amount: float
    dex: DEX
    strategy: ExecutionStrategy
    arbitrage_path: List[str]  # Token addresses in arbitrage path
    gas_limit: int = 300000
    max_slippage: float = 0.005  # 0.5%


@dataclass
class SlippageConfig:
    """Slippage and MEV protection configuration"""
    max_slippage_pct: float = 0.02  # 2%
    min_price_impact_pct: float = 0.01  # 1%
    use_limit_orders: bool = True
    max_gas_price_gwei: float = 50.0
    use_mev_protection: bool = True  # Enable Flashbots/Jito by default
    priority_fee_multiplier: float = 1.2 # Boost gas for institutional execution


class ExecutionLayer:
    """
    Execution Layer - Handles all trade execution operations
    """

    def __init__(
        self,
        trust_wallet,
        market_analyzer,
        slippage_config: SlippageConfig = None
    ):
        """
        Initialize execution layer

        Args:
            trust_wallet: TrustWalletAgent instance
            market_analyzer: MarketDataAnalyzer instance
            slippage_config: Slippage protection configuration
        """
        self.trust_wallet = trust_wallet
        self.market_analyzer = market_analyzer
        self.slippage_config = slippage_config or SlippageConfig()

        # Transaction queue (min-heap by priority)
        self.transaction_queue = []

        # Executed transactions storage
        self.executed_transactions = {}  # tx_id -> Transaction

        # Active flash loans
        self.active_flash_loans = set()

        # Performance metrics
        self.metrics = {
            'total_executions': 0,
            'successful_executions': 0,
            'failed_executions': 0,
            'avg_execution_time': 0,
            'avg_slippage': 0,
            'avg_gas_cost': 0
        }

    def _generate_tx_id(self, token_address: str, amount: float) -> str:
        """Generate unique transaction ID"""
        data = f"{token_address}{amount}{datetime.now().timestamp()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def _calculate_price_impact(
        self,
        expected_price: float,
        actual_price: float
    ) -> PriceImpact:
        """Calculate price impact and slippage"""
        if expected_price == 0:
            raise ValueError("Expected price cannot be zero")

        slippage = abs((actual_price - expected_price) / expected_price)
        impact_percentage = slippage * 100

        return PriceImpact(
            expected_price=expected_price,
            actual_price=actual_price,
            slippage=slippage,
            impact_percentage=impact_percentage
        )

    def _estimate_gas_cost(
        self,
        gas_price: float,
        gas_used: int,
        network: Network
    ) -> float:
        """Estimate transaction cost in native currency"""
        gas_cost = gas_price * gas_used / 1e9  # Convert gwei to ETH

        # Network-specific adjustments
        network_adjustments = {
            Network.ETHEREUM: 1.0,
            Network.BSC: 0.5,  # BSC is cheaper
            Network.ARBITRUM: 0.1,
            Network.OPTIMISM: 0.15,
            Network.POLYGON: 0.2,
            Network.AVALANCHE: 0.3
        }

        return gas_cost * network_adjustments.get(network, 1.0)

    def _get_optimal_dex(
        self,
        token_address: str,
        amount: float,
        strategy: ExecutionStrategy = ExecutionStrategy.BEST_PRICE
    ) -> Tuple[DEX, float]:
        """
        Get optimal DEX based on strategy

        Returns:
            Tuple[DEX, estimated_gas_cost]
        """
        # Get price from multiple DEXs
        price_data = self.market_analyzer.get_price_from_multiple_dexs(
            token_address,
            amount
        )

        if strategy == ExecutionStrategy.BEST_PRICE:
            # Select DEX with best price
            best_dex, best_price = max(price_data.items(), key=lambda x: x[1]['price'])
            return best_dex, best_dex.value['gas_cost']

        elif strategy == ExecutionStrategy.LOWEST_SLIPPAGE:
            # Select DEX with lowest slippage
            best_dex, best_slippage = min(
                price_data.items(),
                key=lambda x: x[1]['slippage']
            )
            return best_dex, best_dex.value['gas_cost']

        elif strategy == ExecutionStrategy.FASTEST_GAS:
            # Select DEX with lowest gas
            best_dex, best_gas = min(
                price_data.items(),
                key=lambda x: x[1]['gas_cost']
            )
            return best_dex, best_dex.value['gas_cost']

        return price_data[0].DEX, price_data[0].value['gas_cost']

    def _validate_slippage(
        self,
        price_impact: PriceImpact,
        token_address: str,
        amount: float
    ) -> bool:
        """Validate slippage against configured limits"""
        # Check individual slippage
        if price_impact.slippage > self.slippage_config.max_slippage_pct:
            return False

        # Check price impact
        if price_impact.impact_percentage < self.slippage_config.min_price_impact_pct:
            # Warning: price impact too low, might be stale data
            print(f"⚠️ Low price impact: {price_impact.impact_percentage:.2f}%")

        return True

    def execute_trade(
        self,
        token_address: str,
        amount: float,
        strategy: ExecutionStrategy = ExecutionStrategy.BEST_PRICE,
        network: Network = Network.ETHEREUM,
        slippage_tolerance: float = 0.02,
        mev_protected: Optional[bool] = None
    ) -> ExecutionResult:
        """
        Execute a trade with slippage protection and optional MEV shielding.

        Args:
            token_address: Token contract address
            amount: Amount to trade
            strategy: Execution strategy
            network: Blockchain network
            slippage_tolerance: Maximum slippage allowed (as percentage)
            mev_protected: Enable Flashbots/Jito (defaults to SlippageConfig value)
        """
        start_time = time.time()
        use_mev = mev_protected if mev_protected is not None else self.slippage_config.use_mev_protection

        try:
            # Get expected price
            expected_price = self.market_analyzer.get_current_price(token_address)

            # Get optimal DEX
            dex, gas_cost = self._get_optimal_dex(token_address, amount, strategy)

            # Create transaction queue entry
            tx_id = self._generate_tx_id(token_address, amount)
            tx = Transaction(
                tx_id=tx_id,
                token_address=token_address,
                amount=amount,
                dex=dex,
                network=network,
                status=TransactionStatus.PENDING,
                created_at=datetime.now(),
                priority=0,
                gas_price=gas_cost * self.slippage_config.priority_fee_multiplier,
                estimated_gas=gas_cost * 100,  # rough estimate
                slippage=slippage_tolerance
            )

            # Add to queue
            heapq.heappush(self.transaction_queue, (0, tx_id, tx))

            # Execute transaction with institutional shielding
            actual_price = self._execute_on_dex(
                token_address=token_address,
                amount=amount,
                dex=dex,
                network=network,
                slippage_tolerance=slippage_tolerance,
                mev_protected=use_mev
            )

            # Calculate price impact
            price_impact = self._calculate_price_impact(expected_price, actual_price)

            # Validate slippage
            if not self._validate_slippage(price_impact, token_address, amount):
                tx.status = TransactionStatus.BLOCKED
                tx.error_message = f"Slippage too high: {price_impact.slippage * 100:.2f}%"

                result = ExecutionResult(
                    success=False,
                    tx_id=tx_id,
                    transaction=tx,
                    actual_amount=amount,
                    actual_slippage=price_impact.slippage,
                    gas_used=0,
                    cost=0,
                    gas_cost=0,
                    message=tx.error_message,
                    execution_time=time.time() - start_time
                )

                self.metrics['failed_executions'] += 1
                return result

            # Record transaction
            tx.status = TransactionStatus.CONFIRMED
            tx.actual_price = actual_price
            self.executed_transactions[tx_id] = tx

            # Calculate execution cost
            gas_price = self.market_analyzer.get_current_gas_price(network)
            gas_used = self.market_analyzer.estimate_gas_needed(dex, token_address, amount)
            gas_cost = self._estimate_gas_cost(gas_price, gas_used, network)

            execution_time = time.time() - start_time

            # Update metrics
            self.metrics['total_executions'] += 1
            self.metrics['successful_executions'] += 1
            
            result = ExecutionResult(
                success=True,
                tx_id=tx_id,
                transaction=tx,
                actual_amount=amount,
                actual_slippage=price_impact.slippage,
                gas_used=gas_used,
                cost=gas_cost,
                gas_cost=gas_cost,
                message=f"Trade executed successfully (MEV Shield: {'ON' if use_mev else 'OFF'})",
                execution_time=execution_time
            )

            return result

        except Exception as e:
            tx_id = self._generate_tx_id(token_address, amount)
            tx = Transaction(
                tx_id=tx_id,
                token_address=token_address,
                amount=amount,
                dex=DEX.UNISWAP_V2,
                network=network,
                status=TransactionStatus.FAILED,
                created_at=datetime.now(),
                error_message=str(e)
            )

            self.executed_transactions[tx_id] = tx
            self.metrics['failed_executions'] += 1

            return ExecutionResult(
                success=False,
                tx_id=tx_id,
                transaction=tx,
                actual_amount=amount,
                actual_slippage=0,
                gas_used=0,
                cost=0,
                gas_cost=0,
                message=f"Execution failed: {str(e)}",
                execution_time=time.time() - start_time
            )

    def _execute_on_dex(
        self,
        token_address: str,
        amount: float,
        dex: DEX,
        network: Network,
        slippage_tolerance: float,
        mev_protected: bool = True
    ) -> float:
        """
        Execute trade on specific DEX with institutional shielding.
        """
        if mev_protected:
            # Determine relay (Flashbots for EVM, Jito for Solana)
            relay = "JITO" if network in [Network.ARBITRUM] else "FLASHBOTS" # Simplified logic
            print(f"🛡️ Routing trade via {relay} private RPC for MEV protection...")

        # Execute on DEX via trust_wallet with protection flags
        actual_price = self.trust_wallet.execute_swap(
            token_address=token_address,
            amount=amount,
            dex=dex.value,
            network=network.value,
            slippage_tolerance=slippage_tolerance,
            use_private_rpc=mev_protected
        )

        return actual_price

    def queue_transaction(
        self,
        token_address: str,
        amount: float,
        dex: DEX,
        network: Network,
        strategy: ExecutionStrategy = ExecutionStrategy.BEST_PRICE,
        priority: int = 0,
        slippage: float = 0.02
    ) -> str:
        """
        Add transaction to queue for later execution

        Args:
            token_address: Token contract address
            amount: Amount to trade
            dex: DEX to use
            network: Blockchain network
            strategy: Execution strategy
            priority: Transaction priority (lower = higher priority)
            slippage: Maximum slippage allowed

        Returns:
            Transaction ID
        """
        tx_id = self._generate_tx_id(token_address, amount)
        tx = Transaction(
            tx_id=tx_id,
            token_address=token_address,
            amount=amount,
            dex=dex,
            network=network,
            status=TransactionStatus.PENDING,
            created_at=datetime.now(),
            priority=priority,
            slippage=slippage
        )

        heapq.heappush(self.transaction_queue, (priority, tx_id, tx))

        return tx_id

    def process_queue(self, max_transactions: int = 1) -> List[ExecutionResult]:
        """
        Process queued transactions

        Args:
            max_transactions: Maximum transactions to process

        Returns:
            List of execution results
        """
        results = []

        for _ in range(max_transactions):
            if not self.transaction_queue:
                break

            # Get highest priority transaction
            priority, tx_id, tx = heapq.heappop(self.transaction_queue)

            # Check if already executed or failed
            if tx_id not in self.executed_transactions:
                # Execute the transaction
                result = self.execute_trade(
                    token_address=tx.token_address,
                    amount=tx.amount,
                    strategy=ExecutionStrategy.BEST_PRICE,
                    network=tx.network,
                    slippage_tolerance=tx.slippage
                )

                results.append(result)

        return results

    def cancel_transaction(self, tx_id: str) -> bool:
        """
        Cancel a pending transaction

        Args:
            tx_id: Transaction ID

        Returns:
            True if cancelled successfully
        """
        # Search for transaction in queue
        for i, (_, queued_tx_id, tx) in enumerate(self.transaction_queue):
            if queued_tx_id == tx_id and tx.status == TransactionStatus.PENDING:
                tx.status = TransactionStatus.CANCELLED
                return True

        # Check executed transactions
        if tx_id in self.executed_transactions:
            tx = self.executed_transactions[tx_id]
            if tx.status == TransactionStatus.PENDING:
                tx.status = TransactionStatus.CANCELLED
                return True

        return False

    def execute_flash_loan_arbitrage(
        self,
        token: str,
        amount: float,
        dex: DEX,
        path: list,
        gas_limit: int,
        max_slippage: float
    ) -> dict:
        """
        Execute arbitrage using flash loan

        Args:
            token: Token address
            amount: Amount to borrow
            dex: DEX to use
            path: Arbitrage path
            gas_limit: Gas limit for the transaction
            max_slippage: Maximum slippage tolerance

        Returns:
            Dictionary with arbitrage results
        """
        if not self.market_analyzer:
            return {
                'profit_percentage': 0.0,
                'gas_cost_usd': 0.0,
                'execution_time': 0.0,
                'error': 'Market analyzer not configured'
            }

        start_time = time.time()

        try:
            # Simulate arbitrage calculation
            profit_percentage = 1.5  # 1.5% profit
            gas_cost_usd = 15.0
            execution_time = time.time() - start_time

            return {
                'profit_percentage': profit_percentage,
                'gas_cost_usd': gas_cost_usd,
                'execution_time': execution_time,
                'tx_hash': '0x' + ''.join([format(i, '02x') for i in range(64)]),
                'source_tx_hash': '0x' + ''.join([format(i, '02x') for i in range(64)])
            }

        except Exception as e:
            return {
                'profit_percentage': 0.0,
                'gas_cost_usd': 0.0,
                'execution_time': time.time() - start_time,
                'error': str(e)
            }

    def execute_arbitrage_with_flash_loan(
        self,
        loan_request: FlashLoanRequest
    ) -> ExecutionResult:
        """
        Execute arbitrage using flash loan (alternative method)

        Args:
            loan_request: Flash loan request parameters

        Returns:
            ExecutionResult
        """
        if loan_request.token in self.active_flash_loans:
            return ExecutionResult(
                success=False,
                tx_id="",
                transaction=None,
                actual_amount=0,
                actual_slippage=0,
                gas_used=0,
                cost=0,
                message="Flash loan already active for this token",
                execution_time=0
            )

        start_time = time.time()

        try:
            self.active_flash_loans.add(loan_request.token)

            # Get loan price
            expected_price = self.market_analyzer.get_current_price(loan_request.token)

            # Execute flash loan arbitrage
            arbitrage_result = self.trust_wallet.execute_flash_loan_arbitrage(
                token=loan_request.token,
                amount=loan_request.amount,
                dex=loan_request.dex.value,
                path=loan_request.arbitrage_path,
                gas_limit=loan_request.gas_limit,
                max_slippage=loan_request.max_slippage
            )

            actual_price = expected_price * (1 + arbitrage_result['profit_percentage'])

            # Create transaction record
            tx_id = self._generate_tx_id(loan_request.token, loan_request.amount)
            tx = Transaction(
                tx_id=tx_id,
                token_address=loan_request.token,
                amount=loan_request.amount,
                dex=loan_request.dex,
                network=Network.ETHEREUM,
                status=TransactionStatus.CONFIRMED,
                created_at=datetime.now(),
                destination_tx_hash=arbitrage_result.get('tx_hash'),
                source_tx_hash=arbitrage_result.get('source_tx_hash')
            )

            self.executed_transactions[tx_id] = tx

            # Calculate gas cost
            gas_price = self.market_analyzer.get_current_gas_price(Network.ETHEREUM)
            gas_used = loan_request.gas_limit
            gas_cost = self._estimate_gas_cost(gas_price, gas_used, Network.ETHEREUM)

            execution_time = time.time() - start_time

            result = ExecutionResult(
                success=True,
                tx_id=tx_id,
                transaction=tx,
                actual_amount=loan_request.amount * arbitrage_result['profit_multiplier'],
                actual_slippage=0.005,  # Maximum 0.5%
                gas_used=gas_used,
                cost=gas_cost,
                gas_cost=gas_cost,
                message=f"Flash loan arbitrage successful: {arbitrage_result['profit_percentage']:.2f}% profit",
                execution_time=execution_time
            )

            return result

        except Exception as e:
            tx_id = self._generate_tx_id(loan_request.token, loan_request.amount)
            tx = Transaction(
                tx_id=tx_id,
                token_address=loan_request.token,
                amount=loan_request.amount,
                dex=loan_request.dex,
                network=Network.ETHEREUM,
                status=TransactionStatus.FAILED,
                created_at=datetime.now(),
                error_message=str(e)
            )

            self.executed_transactions[tx_id] = tx

            return ExecutionResult(
                success=False,
                tx_id=tx_id,
                transaction=tx,
                actual_amount=loan_request.amount,
                actual_slippage=0,
                gas_used=0,
                cost=0,
                gas_cost=0,
                message=f"Flash loan arbitrage failed: {str(e)}",
                execution_time=time.time() - start_time
            )

        finally:
            self.active_flash_loans.discard(loan_request.token)

    def get_transaction_status(self, tx_id: str) -> Optional[Transaction]:
        """Get status of a transaction"""
        return self.executed_transactions.get(tx_id)

    def get_queue_status(self) -> Dict:
        """Get transaction queue status"""
        return {
            'queue_size': len(self.transaction_queue),
            'active_transactions': sum(1 for tx in self.executed_transactions.values()
                                       if tx.status == TransactionStatus.PENDING)
        }

    def get_execution_metrics(self) -> Dict:
        """Get execution performance metrics"""
        return self.metrics

    def optimize_gas(
        self,
        network: Network,
        dex: DEX
    ) -> Dict:
        """
        Optimize gas costs for a DEX and network

        Args:
            network: Blockchain network
            dex: DEX to optimize

        Returns:
            Gas optimization recommendations
        """
        if not self.market_analyzer:
            return {
                'network': network.value,
                'dex': dex.value,
                'current_gas_price_gwei': 0.0,
                'estimated_gas_needed': 0,
                'recommended_gas_price_gwei': 0.0,
                'estimated_cost_wei': 0,
                'estimated_cost_eth': 0.0,
                'gas_multiplier': 1.0,
                'error': 'Market analyzer not configured'
            }

        current_gas_price = self.market_analyzer.get_current_gas_price(network)
        estimated_gas = self.market_analyzer.estimate_gas_needed(dex, "", 1.0)

        recommendations = {
            'network': network.value,
            'dex': dex.value,
            'current_gas_price_gwei': current_gas_price,
            'estimated_gas_needed': estimated_gas,
            'recommended_gas_price_gwei': self._recommend_gas_price(current_gas_price),
            'estimated_cost_wei': estimated_gas * current_gas_price,
            'estimated_cost_eth': (estimated_gas * current_gas_price) / 1e18,
            'gas_multiplier': self._calculate_gas_multiplier(current_gas_price)
        }

        return recommendations

    def _recommend_gas_price(self, current_gas_price: float) -> float:
        """Recommend optimal gas price based on current market"""
        # Use 80% of current price for safety
        return current_gas_price * 0.8

    def _calculate_gas_multiplier(self, gas_price: float) -> float:
        """Calculate gas multiplier recommendation"""
        if gas_price < 20:
            return 0.95  # Market is slow, can save gas
        elif gas_price < 50:
            return 1.0  # Normal market
        else:
            return 1.1  # Market is congested

    def cleanup_expired_transactions(self, max_age_hours: float = 1.0) -> int:
        """
        Clean up expired transactions

        Args:
            max_age_hours: Maximum age of transactions to keep

        Returns:
            Number of transactions cleaned up
        """
        cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)

        cleaned = 0
        for tx_id, tx in self.executed_transactions.items():
            if tx.status == TransactionStatus.PENDING and tx.created_at.timestamp() < cutoff_time:
                tx.status = TransactionStatus.CANCELLED
                cleaned += 1

        return cleaned

    def save_transaction_history(self, filepath: str = "transaction_history.json"):
        """Save transaction history to file"""
        history = [
            {
                'tx_id': tx.tx_id,
                'token': tx.token_address,
                'amount': tx.amount,
                'dex': tx.dex.value,
                'network': tx.network.value,
                'status': tx.status.value,
                'created_at': tx.created_at.isoformat(),
                'slippage': tx.slippage,
                'actual_price': getattr(tx, 'actual_price', None),
                'error': tx.error_message
            }
            for tx in self.executed_transactions.values()
        ]

        with open(filepath, 'w') as f:
            json.dump(history, f, indent=2)

        return filepath

    def print_status(self):
        """Print execution layer status"""
        print("=" * 60)
        print("EXECUTION LAYER STATUS")
        print("=" * 60)

        # Queue status
        queue_status = self.get_queue_status()
        print(f"\n📊 Transaction Queue:")
        print(f"   Pending: {queue_status['active_transactions']}")
        print(f"   Queue Size: {queue_status['queue_size']}")

        # Metrics
        metrics = self.get_execution_metrics()
        print(f"\n📈 Execution Metrics:")
        print(f"   Total Executions: {metrics['total_executions']}")
        print(f"   Successful: {metrics['successful_executions']}")
        print(f"   Failed: {metrics['failed_executions']}")
        print(f"   Success Rate: {(metrics['successful_executions'] / max(metrics['total_executions'], 1) * 100):.2f}%")
        print(f"   Avg Execution Time: {metrics['avg_execution_time']:.2f}s")
        print(f"   Avg Slippage: {metrics['avg_slippage'] * 100:.2f}%")
        print(f"   Avg Gas Cost: ${metrics['avg_gas_cost']:.4f}")

        # Active flash loans
        print(f"\n⚡ Flash Loans:")
        print(f"   Active: {len(self.active_flash_loans)}")

        # Network status
        print(f"\n🪙 Network Status:")
        print(f"   Ethereum Gas: ${self.market_analyzer.get_current_gas_price(Network.ETHEREUM) / 1e9:.4f} gwei")
        print(f"   BSC Gas: ${self.market_analyzer.get_current_gas_price(Network.BSC) / 1e9:.4f} gwei")

        print("\n" + "=" * 60)