from uuid import UUID

from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user_id

test_router = APIRouter()


@test_router.get("/test-auth")
def test_auth(
    current_user_id: UUID = Depends(get_current_user_id),
):
    return {
        "authenticated": True,
        "user_id": str(current_user_id),
    }



from app.auth.auth import supabase

response = supabase.auth.sign_in_with_password({
    "email": "testemail@gmeil.com",
    "password": "testpassword",
})

session = response.session
user = response.user

print("USER ID:")
print(user.id)

print("\nACCESS TOKEN:")
print(session.access_token)