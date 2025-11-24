from google.oauth2 import service_account
from googleapiclient.discovery import build
from fastapi import HTTPException
from ..config import settings


ANDROID_PUBLISHER_SCOPE = "https://www.googleapis.com/auth/androidpublisher"


def _get_publisher_service():
    if not settings.GOOGLE_SERVICE_ACCOUNT_JSON_PATH:
        raise HTTPException(status_code=500, detail="GOOGLE_SERVICE_ACCOUNT_JSON_PATH not configured")
    try:
        credentials = service_account.Credentials.from_service_account_file(
            settings.GOOGLE_SERVICE_ACCOUNT_JSON_PATH,
            scopes=[ANDROID_PUBLISHER_SCOPE],
        )
        service = build("androidpublisher", "v3", credentials=credentials)
        return service
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to initialize Google API client: {e}")


def verify_google_purchase(product_id: str, purchase_token: str):
    if not settings.GOOGLE_PLAY_PACKAGE_NAME:
        raise HTTPException(status_code=500, detail="GOOGLE_PLAY_PACKAGE_NAME not configured")

    service = _get_publisher_service()

    # Try products.get first (in-app item), then fallback to subscriptions.get
    result = None
    is_subscription = False
    try:
        result = (
            service.purchases()
            .products()
            .get(packageName=settings.GOOGLE_PLAY_PACKAGE_NAME, productId=product_id, token=purchase_token)
            .execute()
        )
    except Exception as e_prod:
        # Fallback: attempt subscription check
        try:
            result = (
                service.purchases()
                .subscriptions()
                .get(packageName=settings.GOOGLE_PLAY_PACKAGE_NAME, subscriptionId=product_id, token=purchase_token)
                .execute()
            )
            is_subscription = True
        except Exception as e_sub:
            raise HTTPException(status_code=400, detail=f"Google verification failed: product or subscription not found ({e_prod} / {e_sub})")

    # purchaseState: 0 Purchased, 1 Canceled, 2 Pending (for products)
    # For subscriptions, 'paymentState' may be present (0 pending, 1 received), and 'purchaseType' etc.
    if not is_subscription:
        if result.get("purchaseState") != 0:
            raise HTTPException(status_code=400, detail="Purchase not completed")
    else:
        # Subscriptions may have "paymentState": 1 when payment is received; if missing treat as purchased=1
        payment_state = result.get("paymentState")
        # 'acknowledgementState' exists on both products and subscriptions
        # If payment_state is defined and not 1 (received), treat as not completed
        if payment_state is not None and int(payment_state) != 1:
            raise HTTPException(status_code=400, detail="Subscription payment not completed")

    # Optionally acknowledge if needed
    try:
        if result.get("acknowledgementState") == 0:  # 0: yet to be acknowledged
            if not is_subscription:
                service.purchases().products().acknowledge(
                    packageName=settings.GOOGLE_PLAY_PACKAGE_NAME,
                    productId=product_id,
                    token=purchase_token,
                    body={"developerPayload": "acknowledged-by-zuber"},
                ).execute()
            else:
                service.purchases().subscriptions().acknowledge(
                    packageName=settings.GOOGLE_PLAY_PACKAGE_NAME,
                    subscriptionId=product_id,
                    token=purchase_token,
                    body={"developerPayload": "acknowledged-by-zuber"},
                ).execute()
    except Exception:
        # Non-fatal; acknowledgement can be retried later
        pass

    return result