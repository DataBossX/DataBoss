"""
Pytest configuration and fixtures
"""

import pytest
import asyncio


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def weld_county_mineral_deed_text():
    """Realistic Weld County mineral deed text"""
    return """
    MINERAL DEED

    RECEPTION NO: 2024-000123
    BOOK: 4567 PAGE: 890
    RECORDING DATE: January 15, 2024

    GRANTOR: ROBERT J. HENDERSON and MARY L. HENDERSON, husband and wife

    GRANTEE: WELD ENERGY PARTNERS, LLC, a Colorado limited liability company,
    an undivided 50% interest

    For good and valuable consideration, the receipt and sufficiency of which
    are hereby acknowledged, Grantor hereby grants, bargains, sells, conveys,
    transfers, assigns and delivers unto Grantee all of Grantor's right, title
    and interest in and to all oil, gas and other minerals in, on, under and
    that may be produced from the following described lands:

    LEGAL DESCRIPTION:

    The Northeast Quarter (NE 1/4) of Section 12, Township 5 North,
    Range 68 West of the 6th Principal Meridian, Weld County, Colorado,
    containing 160 acres, more or less.

    DEPTH LIMITATION: From the surface to 5,000 feet below the surface

    TO HAVE AND TO HOLD the same unto Grantee, its successors and assigns forever.

    DATED this 12th day of January, 2024.

    /s/ Robert J. Henderson
    ROBERT J. HENDERSON

    /s/ Mary L. Henderson
    MARY L. HENDERSON

    STATE OF COLORADO   )
                       )ss.
    COUNTY OF WELD     )

    Acknowledged before me this 12th day of January, 2024.

    /s/ Notary Public
    My commission expires: 12/31/2025
    """


@pytest.fixture
def campbell_county_assignment_text():
    """Realistic Campbell County assignment text"""
    return """
    ASSIGNMENT OF OIL AND GAS LEASES

    RECEPTION NO: 2024-567890
    RECORDING DATE: March 20, 2024

    ASSIGNOR: THUNDER BASIN ENERGY COMPANY, a Wyoming corporation

    ASSIGNEE: POWDER RIVER RESOURCES, INC., a Delaware corporation

    WHEREAS, Assignor is the owner of certain oil and gas leases covering
    lands in Campbell County, Wyoming; and

    WHEREAS, Assignee desires to acquire an interest in said leases;

    NOW, THEREFORE, for good and valuable consideration, Assignor hereby
    assigns, transfers and conveys to Assignee an undivided 25% working
    interest in and to the following oil and gas leases:

    1. Oil and Gas Lease dated January 1, 2022, covering:
       Section 24, Township 44 North, Range 73 West, 6th P.M.,
       Campbell County, Wyoming, containing 640 acres.

    DEPTH CLAUSE: From surface to the base of the Niobrara Formation,
    including all rights, privileges and appurtenances thereto.

    Assignee shall be responsible for 25% of all costs and expenses and
    shall be entitled to 25% of all oil, gas and other minerals produced
    from said lands, less royalty and other burdens.

    IN WITNESS WHEREOF, Assignor has executed this Assignment as of
    March 15, 2024.

    THUNDER BASIN ENERGY COMPANY

    By: /s/ James Patterson
    James Patterson, President

    STATE OF WYOMING    )
                        )ss.
    COUNTY OF CAMPBELL  )

    Acknowledged before me this 15th day of March, 2024.

    /s/ Notary Public
    """
