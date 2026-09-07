import asyncio
from dotenv import load_dotenv
load_dotenv()

from app.verification.integrations import kyc_provider

async def test():
    session = await kyc_provider.create_session("individual_kyc", vendor_data="test-user-1")
    print("SUCCESS:", session)
    return session

asyncio.run(test())