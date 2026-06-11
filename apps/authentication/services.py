"""
Business logic for authentication app.

This module contains email services for sending beautifully formatted HTML emails
for user registration, password reset, and OTP verification.
"""

import logging
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger('kibegi')


class EmailService:
    """
    Service for sending beautifully formatted HTML emails.
    
    All emails follow a consistent design with:
    - Kibegi branding
    - Clear OTP display
    - Important security notices
    - Professional footer
    """
    
    # Brand colors
    PRIMARY_COLOR = "#4F46E5"  # Indigo
    PRIMARY_DARK = "#3730A3"   # Darker indigo
    TEXT_COLOR = "#1F2937"     # Gray-800
    TEXT_LIGHT = "#6B7280"     # Gray-500
    BACKGROUND = "#F9FAFB"     # Gray-50
    WHITE = "#FFFFFF"
    SUCCESS = "#10B981"        # Emerald
    WARNING = "#F59E0B"        # Amber
    
    @staticmethod
    def get_base_template(content: str, preview_text: str = "") -> str:
        """
        Generate the base HTML email template with consistent styling.
        
        Args:
            content: The main content HTML to insert
            preview_text: Preview text shown in email clients
            
        Returns:
            Complete HTML email string
        """
        return f'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <title>Kibegi</title>
    <!--[if mso]>
    <noscript>
        <xml>
            <o:OfficeDocumentSettings>
                <o:PixelsPerInch>96</o:PixelsPerInch>
            </o:OfficeDocumentSettings>
        </xml>
    </noscript>
    <![endif]-->
    <style>
        /* Reset styles */
        body, table, td, p, a, li, blockquote {{
            -webkit-text-size-adjust: 100%;
            -ms-text-size-adjust: 100%;
        }}
        table, td {{
            mso-table-lspace: 0pt;
            mso-table-rspace: 0pt;
        }}
        img {{
            -ms-interpolation-mode: bicubic;
            border: 0;
            height: auto;
            line-height: 100%;
            outline: none;
            text-decoration: none;
        }}
        body {{
            margin: 0 !important;
            padding: 0 !important;
            width: 100% !important;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        }}
        /* Responsive styles */
        @media screen and (max-width: 600px) {{
            .container {{
                width: 100% !important;
                padding: 20px !important;
            }}
            .otp-code {{
                font-size: 28px !important;
                letter-spacing: 6px !important;
            }}
        }}
    </style>
</head>
<body style="margin: 0; padding: 0; background-color: {EmailService.BACKGROUND};">
    <!-- Preview text -->
    <div style="display: none; max-height: 0; overflow: hidden;">
        {preview_text}
        &nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;
    </div>
    
    <!-- Main container -->
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: {EmailService.BACKGROUND};">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <!-- Email content wrapper -->
                <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="600" class="container" style="background-color: {EmailService.WHITE}; border-radius: 16px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);">
                    
                    <!-- Header with logo -->
                    <tr>
                        <td style="padding: 40px 40px 30px 40px; text-align: center; border-bottom: 1px solid #E5E7EB;">
                            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                                <tr>
                                    <td align="center">
                                        <!-- Logo/Brand -->
                                        <div style="display: inline-block; background: linear-gradient(135deg, {EmailService.PRIMARY_COLOR} 0%, {EmailService.PRIMARY_DARK} 100%); padding: 12px 24px; border-radius: 12px;">
                                            <span style="font-size: 28px; font-weight: 700; color: {EmailService.WHITE}; letter-spacing: 1px;">📚 Kibegi</span>
                                        </div>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    
                    <!-- Main content -->
                    {content}
                    
                    <!-- Footer -->
                    <tr>
                        <td style="padding: 30px 40px 40px 40px; background-color: {EmailService.BACKGROUND}; border-radius: 0 0 16px 16px;">
                            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                                <tr>
                                    <td align="center" style="padding-bottom: 15px;">
                                        <p style="margin: 0; font-size: 13px; color: {EmailService.TEXT_LIGHT}; line-height: 1.6;">
                                            This is an automated message from Kibegi.<br>
                                            Please do not reply to this email.
                                        </p>
                                    </td>
                                </tr>
                                <tr>
                                    <td align="center">
                                        <p style="margin: 0; font-size: 12px; color: {EmailService.TEXT_LIGHT};">
                                            © {settings.CURRENT_YEAR if hasattr(settings, 'CURRENT_YEAR') else '2025'} Kibegi. All rights reserved.
                                        </p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
'''

    @staticmethod
    def get_otp_content(
        user_name: str,
        otp_code: str,
        expiry_minutes: int,
        purpose: str = "verification",
        additional_message: str = ""
    ) -> str:
        """
        Generate the OTP display content block.
        
        Args:
            user_name: User's display name
            otp_code: The OTP code to display
            expiry_minutes: How long the OTP is valid
            purpose: 'registration' or 'password_reset'
            additional_message: Optional additional message
            
        Returns:
            HTML content block for OTP display
        """
        # Determine welcome message based on purpose
        if purpose == "registration":
            title = "Welcome to Kibegi!"
            intro = "Thank you for registering with Kibegi. To complete your account verification, please use the following One-Time Password (OTP):"
            outro = "Once verified, you'll be able to access all Kibegi features including class management, file uploads, and collaborative learning!"
        elif purpose == "password_reset":
            title = "Password Reset Request"
            intro = "We received a request to reset your password. Use the following One-Time Password (OTP) to proceed:"
            outro = "After verification, you'll be able to set a new password for your account."
        else:
            title = "Verification Code"
            intro = "Please use the following One-Time Password (OTP) to complete your request:"
            outro = ""
        
        return f'''
                    <tr>
                        <td style="padding: 40px 40px 20px 40px;">
                            <!-- Greeting -->
                            <h1 style="margin: 0 0 20px 0; font-size: 24px; font-weight: 700; color: {EmailService.TEXT_COLOR}; text-align: center;">
                                {title}
                            </h1>
                            
                            <!-- User name greeting -->
                            <p style="margin: 0 0 25px 0; font-size: 16px; color: {EmailService.TEXT_COLOR}; text-align: center;">
                                Hello <strong>{user_name}</strong>! 👋
                            </p>
                            
                            <!-- Introduction text -->
                            <p style="margin: 0 0 30px 0; font-size: 15px; color: {EmailService.TEXT_LIGHT}; line-height: 1.6; text-align: center;">
                                {intro}
                            </p>
                        </td>
                    </tr>
                    
                    <!-- OTP Code Display -->
                    <tr>
                        <td style="padding: 0 40px;">
                            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                                <tr>
                                    <td align="center">
                                        <div style="background: linear-gradient(135deg, {EmailService.PRIMARY_COLOR}15 0%, {EmailService.PRIMARY_DARK}15 100%); border: 2px dashed {EmailService.PRIMARY_COLOR}; border-radius: 12px; padding: 25px 40px; display: inline-block;">
                                            <span class="otp-code" style="font-size: 36px; font-weight: 700; color: {EmailService.PRIMARY_COLOR}; letter-spacing: 8px; font-family: 'Courier New', Courier, monospace;">
                                                {otp_code}
                                            </span>
                                        </div>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    
                    <!-- Important notices -->
                    <tr>
                        <td style="padding: 30px 40px 20px 40px;">
                            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #FEF3C7; border-radius: 8px; border-left: 4px solid {EmailService.WARNING};">
                                <tr>
                                    <td style="padding: 20px;">
                                        <p style="margin: 0 0 10px 0; font-size: 14px; font-weight: 600; color: {EmailService.TEXT_COLOR};">
                                            ⚠️ Important:
                                        </p>
                                        <ul style="margin: 0; padding-left: 20px; color: {EmailService.TEXT_COLOR}; font-size: 14px; line-height: 1.8;">
                                            <li>This OTP is valid for <strong>{expiry_minutes} minutes</strong> only</li>
                                            <li>Do not share this code with anyone</li>
                                            <li>If you didn't request this verification, please ignore this email</li>
                                        </ul>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    
                    <!-- Outro message -->
                    <tr>
                        <td style="padding: 10px 40px 30px 40px;">
                            <p style="margin: 0; font-size: 15px; color: {EmailService.TEXT_LIGHT}; line-height: 1.6; text-align: center;">
                                {outro}
                            </p>
                            {f'<p style="margin: 15px 0 0 0; font-size: 14px; color: {EmailService.TEXT_LIGHT}; text-align: center;">{additional_message}</p>' if additional_message else ''}
                        </td>
                    </tr>
'''

    @classmethod
    def send_registration_otp(
        cls,
        email: str,
        user_name: str,
        otp_code: str,
        expiry_minutes: int = 10
    ) -> bool:
        """
        Send registration verification OTP email.
        
        Args:
            email: Recipient email address
            user_name: User's display name
            otp_code: The OTP code
            expiry_minutes: OTP validity period in minutes
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        subject = "🔐 Your Kibegi Registration Code"
        preview_text = f"Your verification code is {otp_code}. Valid for {expiry_minutes} minutes."
        
        content = cls.get_otp_content(
            user_name=user_name,
            otp_code=otp_code,
            expiry_minutes=expiry_minutes,
            purpose="registration"
        )
        
        html_content = cls.get_base_template(content, preview_text)
        plain_text = f"""
Welcome to Kibegi, {user_name}!

Your registration verification code is: {otp_code}

This code will expire in {expiry_minutes} minutes.

Important:
- Do not share this code with anyone
- If you didn't request this, please ignore this email

© 2025 Kibegi. All rights reserved.
"""
        
        return cls._send_email(email, subject, plain_text, html_content)
    
    @classmethod
    def send_password_reset_otp(
        cls,
        email: str,
        user_name: str,
        otp_code: str,
        expiry_minutes: int = 10
    ) -> bool:
        """
        Send password reset OTP email.
        
        Args:
            email: Recipient email address
            user_name: User's display name
            otp_code: The OTP code
            expiry_minutes: OTP validity period in minutes
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        subject = "🔑 Kibegi Password Reset Code"
        preview_text = f"Your password reset code is {otp_code}. Valid for {expiry_minutes} minutes."
        
        content = cls.get_otp_content(
            user_name=user_name,
            otp_code=otp_code,
            expiry_minutes=expiry_minutes,
            purpose="password_reset"
        )
        
        html_content = cls.get_base_template(content, preview_text)
        plain_text = f"""
Password Reset Request

Hello {user_name},

Your password reset code is: {otp_code}

This code will expire in {expiry_minutes} minutes.

Important:
- Do not share this code with anyone
- If you didn't request this, please ignore this email

© 2025 Kibegi. All rights reserved.
"""
        
        return cls._send_email(email, subject, plain_text, html_content)
    
    @classmethod
    def send_resend_otp(
        cls,
        email: str,
        user_name: str,
        otp_code: str,
        expiry_minutes: int = 10,
        purpose: str = "registration"
    ) -> bool:
        """
        Send resent OTP email (for both registration and password reset).
        
        Args:
            email: Recipient email address
            user_name: User's display name
            otp_code: The OTP code
            expiry_minutes: OTP validity period in minutes
            purpose: 'registration' or 'password_reset'
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        if purpose == "registration":
            subject = "🔐 Your New Kibegi Registration Code"
            preview_text = f"Your new verification code is {otp_code}."
        else:
            subject = "🔑 Your New Kibegi Password Reset Code"
            preview_text = f"Your new password reset code is {otp_code}."
        
        content = cls.get_otp_content(
            user_name=user_name,
            otp_code=otp_code,
            expiry_minutes=expiry_minutes,
            purpose=purpose,
            additional_message="This is a new code. Your previous code has been invalidated."
        )
        
        html_content = cls.get_base_template(content, preview_text)
        plain_text = f"""
{'Registration' if purpose == 'registration' else 'Password Reset'} Code Resent

Hello {user_name},

Your new {'verification' if purpose == 'registration' else 'password reset'} code is: {otp_code}

This code will expire in {expiry_minutes} minutes.
Your previous code has been invalidated.

Important:
- Do not share this code with anyone
- If you didn't request this, please ignore this email

© 2025 Kibegi. All rights reserved.
"""
        
        return cls._send_email(email, subject, plain_text, html_content)
    
    @classmethod
    def send_lecturer_approved(cls, email: str, user_name: str) -> bool:
        subject = "🎉 Your Kibegi Lecturer Account Has Been Approved"
        preview_text = "Your lecturer account on Kibegi is now active."
        content = f'''
                    <tr>
                        <td style="padding: 40px 40px 30px 40px; text-align: center;">
                            <h1 style="margin: 0 0 20px 0; font-size: 24px; font-weight: 700; color: {cls.TEXT_COLOR};">
                                Account Approved!
                            </h1>
                            <p style="margin: 0 0 20px 0; font-size: 16px; color: {cls.TEXT_COLOR};">
                                Hello <strong>{user_name}</strong>! 👋
                            </p>
                            <p style="margin: 0 0 20px 0; font-size: 15px; color: {cls.TEXT_LIGHT}; line-height: 1.6;">
                                Great news! Your lecturer account on Kibegi has been reviewed and approved by our admin team.
                                You can now log in and start creating classes, uploading materials, and managing your students.
                            </p>
                            <div style="background-color: #D1FAE5; border-radius: 8px; padding: 20px; border-left: 4px solid {cls.SUCCESS};">
                                <p style="margin: 0; font-size: 15px; color: {cls.TEXT_COLOR}; font-weight: 600;">
                                    ✅ Your account is now active. Log in to get started!
                                </p>
                            </div>
                        </td>
                    </tr>
'''
        html_content = cls.get_base_template(content, preview_text)
        plain_text = f"Hello {user_name},\n\nYour Kibegi lecturer account has been approved. You can now log in.\n\n© 2025 Kibegi."
        return cls._send_email(email, subject, plain_text, html_content)

    @classmethod
    def send_lecturer_rejected(cls, email: str, user_name: str) -> bool:
        subject = "Kibegi Lecturer Account Application Update"
        preview_text = "An update regarding your Kibegi lecturer account application."
        content = f'''
                    <tr>
                        <td style="padding: 40px 40px 30px 40px; text-align: center;">
                            <h1 style="margin: 0 0 20px 0; font-size: 24px; font-weight: 700; color: {cls.TEXT_COLOR};">
                                Account Application Update
                            </h1>
                            <p style="margin: 0 0 20px 0; font-size: 16px; color: {cls.TEXT_COLOR};">
                                Hello <strong>{user_name}</strong>,
                            </p>
                            <p style="margin: 0 0 20px 0; font-size: 15px; color: {cls.TEXT_LIGHT}; line-height: 1.6;">
                                After reviewing your lecturer account application, we are unable to approve your account at this time.
                                If you believe this is an error, please contact our support team for assistance.
                            </p>
                        </td>
                    </tr>
'''
        html_content = cls.get_base_template(content, preview_text)
        plain_text = f"Hello {user_name},\n\nYour Kibegi lecturer account application was not approved. Contact support if you need assistance.\n\n© 2025 Kibegi."
        return cls._send_email(email, subject, plain_text, html_content)

    @classmethod
    def _send_email(
        cls,
        to_email: str,
        subject: str,
        plain_text: str,
        html_content: str
    ) -> bool:
        """
        Internal method to send an email with both HTML and plain text versions.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            plain_text: Plain text version of the email
            html_content: HTML version of the email
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None)
        
        if not from_email:
            logger.warning("DEFAULT_FROM_EMAIL not configured. Cannot send email.")
            return False
        
        try:
            # Create email with both plain text and HTML
            email = EmailMultiAlternatives(
                subject=subject,
                body=plain_text,
                from_email=from_email,
                to=[to_email]
            )
            
            # Attach HTML version
            email.attach_alternative(html_content, "text/html")
            
            # Send the email
            email.send(fail_silently=False)
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False
