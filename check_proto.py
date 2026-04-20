import google.ai.generativelanguage as gapic
from google.protobuf import descriptor

def check():
    fc = gapic.FunctionCall()
    field = fc.DESCRIPTOR.fields_by_name['id']
    print(f"FunctionCall.id type: {field.type} ({'STRING' if field.type == 9 else 'BYTES' if field.type == 12 else field.type})")
    
    p = gapic.Part()
    if 'thought_signature' in p.DESCRIPTOR.fields_by_name:
        field = p.DESCRIPTOR.fields_by_name['thought_signature']
        print(f"Part.thought_signature type: {field.type} ({'STRING' if field.type == 9 else 'BYTES' if field.type == 12 else field.type})")
    else:
        print("Part.thought_signature field not found in this proto version.")

if __name__ == "__main__":
    check()
