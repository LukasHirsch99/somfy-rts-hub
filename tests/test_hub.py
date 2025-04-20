import somfyhub
import pytest

HOST = "10.0.0.99"
PORT = 42069

hub = somfyhub.SomfyHub(HOST, PORT)


# @pytest.mark.asyncio
# async def test_getAllCovers():
#     r = await hub.getAllCovers()
#     assert r.status == somfyhub.STATUS.SUCCESS
#     print(", ".join(str(c) for c in r.body))


@pytest.mark.asyncio
async def test_addCover():
    r = await hub.addCover("test_addCover", 2)
    print(r.status)
    print("Body: " + r.body)
    assert r.status == somfyhub.STATUS.SUCCESS


# @pytest.mark.asyncio
# async def test_renameCover():
#     r = await hub.renameCover(2, "test_renameCover")
#     print(r.status)
#     print(r.body)
#     assert r.status == somfyhub.STATUS.SUCCESS
#
#
# @pytest.mark.asyncio
# async def test_removeCover():
#     r = await hub.removeCover(2)
#     print(r.status)
#     print(r.body)
#     assert r.status == somfyhub.STATUS.SUCCESS
