from pywebpush import webpush

sub_info = {
    "endpoint": "https://fcm.googleapis.com/fcm/send/test",
    "keys": {"p256dh": "test", "auth": "test"}
}

key = "-----BEGIN PRIVATE KEY-----\nMIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgN06qWGKWR0PhmsRS\nH9rvhL0IfKKiV7G9KnRPKwJdY2ehRANCAAQnA4yYKI6zeCaFPNtX5TOCOfm9f4U0\nURaLiprnP0075uHinzUG8fvucHxJE4jkcDfAxOQYIhlCBdWWgYw0suz9\n-----END PRIVATE KEY-----"

print("Testing PEM string directly:")
try:
    webpush(subscription_info=sub_info, data="test", vapid_private_key=key, vapid_claims={"sub": "mailto:test@test.com"})
    print("Success!")
except Exception as e:
    print("Failed:", type(e).__name__, str(e))

print("\nTesting writing to file and passing file path:")
with open("temp_vapid.pem", "w") as f:
    f.write(key)
try:
    webpush(subscription_info=sub_info, data="test", vapid_private_key="temp_vapid.pem", vapid_claims={"sub": "mailto:test@test.com"})
    print("Success with file path!")
except Exception as e:
    print("Failed with file path:", type(e).__name__, str(e))
