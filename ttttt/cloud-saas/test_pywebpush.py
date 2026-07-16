from pywebpush import webpush

sub_info = {
    "endpoint": "https://fcm.googleapis.com/fcm/send/test",
    "keys": {"p256dh": "test", "auth": "test"}
}

key = "d_9HCFN4Pqk2vIPMPv4Fgi5V-S3jhiglQa8RGqmU56o"

print(f"\n--- Testing Key: {key} ---")
try:
    webpush(subscription_info=sub_info, data="test", vapid_private_key=key, vapid_claims={"sub": "mailto:test@test.com"})
    print("Success!")
except Exception as e:
    print("Failed:", type(e).__name__, str(e))
