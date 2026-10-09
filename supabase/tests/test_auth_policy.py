import json
from pathlib import Path
import re


SUPABASE = Path(__file__).parents[1]
POLICY = json.loads((SUPABASE / "auth-policy.json").read_text())


def test_deferred_otp_template_matches_future_code_and_expiration():
    email = POLICY["future_email_otp"]
    assert not email["enabled"]
    template = (SUPABASE / email["template"]).read_text()
    tokens = re.findall(r"{{\s*\.([A-Za-z]+)\s*}}", template)
    assert tokens == ["Token"]  # Code entry must not silently become Magic Link login.
    assert email["otp_length"] == 6
    minutes = email["otp_expiry_seconds"] // 60
    assert f"{minutes} 分钟" in template
    assert 60 <= email["resend_interval_seconds"] < email["otp_expiry_seconds"]


def test_current_release_policy_is_email_password_without_verification():
    assert POLICY["mode"] == "email_password_mvp"
    assert POLICY["email"]["enabled"] and POLICY["email"]["allow_signup"]
    assert POLICY["email"]["password_login"]
    assert not POLICY["email"]["require_verification"]
    assert not POLICY["email"]["otp_login"]
    assert not POLICY["email"]["magic_link_login"]
    assert not POLICY["phone"]["enabled"]
    assert not POLICY["anonymous_sign_in"]["enabled"]
    # This artifact must not claim it automatically configures hosted Auth.
    assert POLICY["deployment"]["kind"] == "desired_policy_not_applied_hosted_configuration"


def test_mvp_has_no_email_delivery_dependency():
    assert not POLICY["delivery"]["required_for_mvp"]
    assert POLICY["delivery"]["status"] == "deferred"
    assert POLICY["delivery"]["password_recovery"] == "deferred"
    assert POLICY["future_email_otp"]["requires_verified_sender_and_delivery_acceptance"]


def test_incremental_auth_sql_matches_standalone_schema():
    schema = (SUPABASE / "schema.sql").read_text()
    incremental = (SUPABASE / "auth.sql").read_text()
    start = "create or replace function public.handle_new_user()"
    schema_function = schema.split(start, 1)[1].split("$$;", 1)[0]
    auth_function = incremental.split(start, 1)[1].split("$$;", 1)[0]
    assert auth_function == schema_function
    backfill = incremental.split("insert into public.profiles (id, display_name)\nselect", 1)[1].split(";", 1)[0]
    assert "insert into public.profiles (id, display_name)\nselect" + backfill in schema
