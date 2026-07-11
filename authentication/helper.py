from django.utils import timezone
from .models import OTP, User
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

def send_otp(email, task="verification"):
    try:
        user = User.objects.get(email=email)
        otp_obj = OTP.generate_otp(user)
        
        subject = f"Your OTP for {task}"
        html_message = render_to_string('otp_email.html', {'otp': otp_obj.otp})
        plain_message = strip_tags(html_message)
        email_from = settings.EMAIL_HOST_USER
        recipient_list = [email]
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=email_from,
            recipient_list=recipient_list,
            html_message=html_message
        )
        
        return {"status": True, "log": f"OTP sent successfully to {email}"}
    except User.DoesNotExist:
        return {"status": False, "log": "User with this email does not exist."}
    except Exception as e:
        return {"status": False, "log": str(e)}


def verify_otp(email, otp_code):
    try:
        otp_obj = OTP.objects.filter(user__email=email).latest('created_at')
    except OTP.DoesNotExist:
        return {"status": False, "log": "Invalid OTP or email."}

    # Check expiry
    if otp_obj.is_expired():
        return {"status": False, "log": "OTP has expired."}

    # Verify OTP
    if otp_obj.otp != otp_code:
        return {"status": False, "log": "Invalid OTP."}

    # OTP verified, activate user & delete OTP
    user = otp_obj.user
    user.is_active = True
    user.save()
    otp_obj.delete()

    return {"status": True, "log": "OTP verified statusfully."}
