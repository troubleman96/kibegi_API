from rest_framework.response import Response
from rest_framework import status


def api_response(success=True, message="", data=None, errors=None, status_code=status.HTTP_200_OK):
    """
    Standard API response format used across the project.

    Args:
        success (bool): Whether the request was successful.
        message (str): Human-friendly message.
        data (dict|list|None): Payload (user, tokens, profile, etc.).
        errors (dict|list|None): Validation errors or system errors.
        status_code (int): HTTP status code.

    Returns:
        Response: DRF Response object with standardized JSON.
    """
    return Response(
        {
            "success": success,
            "message": message,
            "data": data,
            "errors": errors,
        },
        status=status_code,
    )


def success_response(data=None, message="Success", status_code=status.HTTP_200_OK):
    """Helper function for successful responses"""
    return api_response(
        success=True,
        message=message,
        data=data,
        status_code=status_code
    )


def error_response(message="Error", errors=None, status_code=status.HTTP_400_BAD_REQUEST):
    """Helper function for error responses"""
    return api_response(
        success=False,
        message=message,
        errors=errors,
        status_code=status_code
    )
