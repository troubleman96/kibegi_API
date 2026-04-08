"""Code generation utilities"""
import random
import string


def generate_code(length=6, chars=string.digits):
    """
    Generate a random code of specified length.
    
    Args:
        length (int): Length of the code to generate
        chars (str): Character set to use for generation
        
    Returns:
        str: Generated code
    """
    return ''.join(random.choice(chars) for _ in range(length))


def generate_numeric_code(length=6):
    """Generate a numeric code (digits only)"""
    return generate_code(length, string.digits)


def generate_alphanumeric_code(length=8):
    """Generate an alphanumeric code"""
    return generate_code(length, string.ascii_uppercase + string.digits)


def generate_unique_code(model_class, field_name, length=8):
    """
    Generate a unique code for a model field.
    
    Args:
        model_class: The Django model class
        field_name (str): The name of the field to check uniqueness
        length (int): Length of the code to generate
        
    Returns:
        str: A unique alphanumeric code
    """
    while True:
        code = generate_alphanumeric_code(length)
        if not model_class.objects.filter(**{field_name: code}).exists():
            return code
