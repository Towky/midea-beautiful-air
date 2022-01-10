import json
from typing import Final
import pytest

from requests.exceptions import RequestException
import requests_mock

from midea_beautiful.cloud import MideaCloud
from midea_beautiful.exceptions import (
    CloudAuthenticationError,
    CloudError,
    CloudRequestError,
    RetryLaterError,
)
from midea_beautiful.midea import DEFAULT_APP_ID, DEFAULT_APPKEY

_j = json.dumps

DUMMY_RQ: Final = {"arg1": "value1"}


@pytest.fixture(name="appliance_list")
def appliance_list(requests_mock: requests_mock.Mocker):
    requests_mock.post(
        "https://mapp.appsmb.com/v1/homegroup/list/get",
        text=_j(
            {
                "errorCode": "0",
                "result": {"list": [{"isDefault": "1", "id": "group-id-1"}]},
            }
        ),
    )
    requests_mock.post(
        "https://mapp.appsmb.com/v1/appliance/list/get",
        text=_j({"errorCode": "0", "result": {"list": [{"id": "1"}, {"id": "2"}]}}),
    )
    return requests_mock


@pytest.fixture(name="cloud_client")
def cloud_client() -> MideaCloud:
    return MideaCloud(
        appkey=DEFAULT_APPKEY,
        appid=DEFAULT_APP_ID,
        account="user@example.com",
        password="pa55word",
    )


@pytest.fixture(name="for_login")
def for_login(requests_mock: requests_mock.Mocker):
    requests_mock.post(
        "https://mapp.appsmb.com/v1/user/login/id/get",
        text=_j({"errorCode": "0", "result": {"loginId": "test-login"}}),
    )
    requests_mock.post(
        "https://mapp.appsmb.com/v1/user/login",
        text=_j(
            {
                "errorCode": "0",
                "result": {
                    "sessionId": "session-1",
                    "accessToken": "87836529d24810fb715db61f2d3eba2ab920ebb829d567559397ded751813801",  # noqa: E501
                },
            }
        ),
    )
    return requests_mock


def test_str(cloud_client: MideaCloud):
    assert "_appkey" in str(cloud_client)
    assert "3742e9e5842d4ad59c2db887e12449f9" in str(cloud_client)


def test_request_handling(
    cloud_client: MideaCloud, requests_mock: requests_mock.Mocker
):
    requests_mock.post(
        "https://mapp.appsmb.com/v1/dummy", text=_j({"result": "response text"})
    )
    response = cloud_client.api_request("dummy", DUMMY_RQ, authenticate=False)
    assert "response text" == response


def test_request_missing_result(
    cloud_client: MideaCloud, requests_mock: requests_mock.Mocker
):
    requests_mock.post(
        "https://mapp.appsmb.com/v1/dummy",
        text=_j({"response": "response text"}),
    )
    response = cloud_client.api_request("dummy", DUMMY_RQ, authenticate=False)
    assert response is None


def test_request_error(cloud_client: MideaCloud, requests_mock: requests_mock.Mocker):
    requests_mock.post(
        "https://mapp.appsmb.com/v1/dummy",
        text=_j({"errorCode": "2", "msg": "error message"}),
    )
    with pytest.raises(CloudError) as ex:
        cloud_client.api_request("dummy", DUMMY_RQ, authenticate=False)
    assert "error message" == ex.value.message
    assert 2 == ex.value.error_code
    assert "Midea cloud API error 2 error message" == str(ex.value)


def test_request_retry(cloud_client: MideaCloud, requests_mock: requests_mock.Mocker):
    requests_mock.post(
        "https://mapp.appsmb.com/v1/dummy",
        text=_j({"errorCode": "7610", "msg": "retry error message"}),
    )
    with pytest.raises(RetryLaterError) as ex:
        cloud_client.api_request("dummy", DUMMY_RQ, authenticate=False)
    assert "retry error message" == ex.value.message
    assert "Retry later 7610 retry error message" == str(ex.value)


def test_request_authentication_error(
    cloud_client: MideaCloud, requests_mock: requests_mock.Mocker
):
    requests_mock.post(
        "https://mapp.appsmb.com/v1/dummy",
        text=_j({"errorCode": "3102", "msg": "authentication error"}),
    )
    with pytest.raises(CloudAuthenticationError) as ex:
        cloud_client.api_request("dummy", DUMMY_RQ, authenticate=False)
    assert "authentication error" == ex.value.message
    assert 3102 == ex.value.error_code
    assert "Authentication 3102 authentication error" == str(ex.value)


def test_request_too_many_retries(
    cloud_client: MideaCloud, requests_mock: requests_mock.Mocker
):
    requests_mock.post(
        "https://mapp.appsmb.com/v1/too-many-retries",
        text=_j({"errorCode": "9999", "msg": "internal error - ignore"}),
    )
    with pytest.raises(CloudRequestError) as ex:
        cloud_client.api_request("too-many-retries", DUMMY_RQ, authenticate=False)
    assert "Too many retries while calling too-many-retries" == ex.value.message


def test_request_exception(
    cloud_client: MideaCloud, requests_mock: requests_mock.Mocker
):
    requests_mock.post(
        "https://mapp.appsmb.com/v1/exception",
        exc=RequestException("simulated"),
    )
    with pytest.raises(CloudRequestError) as ex:
        cloud_client.api_request("exception", DUMMY_RQ, authenticate=False)
    assert "Request error simulated while calling exception" == ex.value.message


def test_session_restart(cloud_client: MideaCloud, requests_mock: requests_mock.Mocker):
    cloud = cloud_client

    requests_mock.post(
        "https://mapp.appsmb.com/v1/dummy",
        [
            {"text": '{"errorCode": "3106", "msg": "session restart"}'},
            {"text": _j({"result": "response text"})},
        ],
    )
    requests_mock.post(
        "https://mapp.appsmb.com/v1/user/login/id/get",
        text=_j({"errorCode": "0", "result": {"loginId": "test-login"}}),
    )
    requests_mock.post(
        "https://mapp.appsmb.com/v1/user/login",
        text=_j(
            {
                "errorCode": "0",
                "result": {
                    "sessionId": "session-1",
                    "accessToken": "87836529d24810fb715db61f2d3eba2ab920ebb829d567559397ded751813801",  # noqa E501
                },
            }
        ),
    )
    requests_mock.post(
        "https://mapp.appsmb.com/v1/homegroup/list/get",
        text=_j({"errorCode": "0", "result": {"loginId": "test-login"}}),
    )
    result = cloud.api_request("dummy", DUMMY_RQ, authenticate=False)
    assert "response text" == result
    history = requests_mock.request_history

    assert history[0].url == "https://mapp.appsmb.com/v1/dummy"
    assert history[1].url == "https://mapp.appsmb.com/v1/user/login/id/get"
    assert history[2].url == "https://mapp.appsmb.com/v1/user/login"
    assert history[3].url == "https://mapp.appsmb.com/v1/dummy"


def test_full_restart(
    cloud_client: MideaCloud,
    requests_mock: requests_mock.Mocker,
    for_login,
    appliance_list,
):
    requests_mock.post(
        "https://mapp.appsmb.com/v1/dummy",
        [
            {"text": _j({"errorCode": "3144", "msg": "full restart"})},
            {"text": _j({"result": "successful"})},
        ],
    )
    result = cloud_client.api_request("dummy", DUMMY_RQ, authenticate=False)
    assert "successful" == result
    assert "test-login" == cloud_client._login_id
    assert "session-1" == cloud_client._session["sessionId"]
    history = requests_mock.request_history
    assert history[0].url == "https://mapp.appsmb.com/v1/dummy"
    assert history[1].url == "https://mapp.appsmb.com/v1/user/login/id/get"
    assert history[2].url == "https://mapp.appsmb.com/v1/user/login"
    assert history[3].url == "https://mapp.appsmb.com/v1/homegroup/list/get"
    assert history[4].url == "https://mapp.appsmb.com/v1/appliance/list/get"
    assert history[5].url == "https://mapp.appsmb.com/v1/dummy"


def test_full_restart_retries(
    cloud_client: MideaCloud,
    requests_mock: requests_mock.Mocker,
    for_login,
    appliance_list,
):
    requests_mock.post(
        "https://mapp.appsmb.com/v1/full_restart",
        text=_j({"errorCode": "3144", "msg": "full restart"}),
    )
    with pytest.raises(CloudRequestError) as ex:
        cloud_client.api_request("full_restart", DUMMY_RQ, authenticate=False)
    assert "Too many retries while calling full_restart" == ex.value.message


def test_list_appliance(
    cloud_client: MideaCloud,
    requests_mock: requests_mock.Mocker,
    for_login,
    appliance_list,
):
    list = cloud_client.list_appliances()
    assert 2 == len(list)

    cloud_client._appliance_list = [{}]
    list = cloud_client.list_appliances()
    assert 1 == len(list)
    list = cloud_client.list_appliances(force=True)
    assert 2 == len(list)


def test_homegroup_no_default(
    cloud_client: MideaCloud,
    requests_mock: requests_mock.Mocker,
    for_login,
    appliance_list,
):
    requests_mock.post(
        "https://mapp.appsmb.com/v1/homegroup/list/get",
        text=_j(
            {
                "errorCode": "0",
                "result": {
                    "list": [
                        {"isDefault": "0", "id": "group-id-1"},
                        {"isDefault": "0", "id": "group-id-2"},
                    ]
                },
            }
        ),
    )
    with pytest.raises(CloudRequestError) as ex:
        cloud_client.list_appliances(force=True)
    assert "Unable to get default home group from Midea API" == ex.value.message


def test_no_homegroups(
    cloud_client: MideaCloud,
    requests_mock: requests_mock.Mocker,
    for_login,
    appliance_list,
):
    requests_mock.post(
        "https://mapp.appsmb.com/v1/homegroup/list/get",
        text=_j({"errorCode": "0", "result": {}}),
    )
    with pytest.raises(CloudRequestError) as ex:
        cloud_client.list_appliances(force=True)
    assert "Unable to get home groups from Midea API" == ex.value.message


def test_get_token(
    cloud_client: MideaCloud, requests_mock: requests_mock.Mocker, for_login
):
    requests_mock.post(
        "https://mapp.appsmb.com/v1/iot/secure/getToken",
        text=_j(
            {
                "errorCode": "0",
                "result": {
                    "tokenlist": [
                        {"udpId": "2", "token": "token-2", "key": "key-2"},
                        {"udpId": "1", "token": "token-1", "key": "key-1"},
                    ]
                },
            }
        ),
    )
    token, key = cloud_client.get_token("1")
    assert "token-1" == token
    assert "key-1" == key

    token, key = cloud_client.get_token("2")
    assert "token-2" == token
    assert "key-2" == key

    token, key = cloud_client.get_token("absent")
    assert "" == token
    assert "" == key


def test_appliance_transparent_send(cloud_client, for_login):
    for_login.post(
        "https://mapp.appsmb.com/v1/appliance/transparent/send",
        text=_j(
            {
                "errorCode": "0",
                "result": {
                    "reply": (
                        "7c8911b6de8e29fa9a1538def06c9018a9995980893554fb80fd87"
                        "c5478ac78b360f7b35433b8d451464bdcd3746c4f5c05a8099eceb"
                        "79aeb9cc2cc712f90f1c9b3bb091bcf0e90bddf62d36f29550796c"
                        "55acf8e637f7d3d68d11be993df933d94b2b43763219c85eb21b4d"
                        "9bb9891f1ab4ccf24185ccbcc78c393a9212c24bef3466f9b3f18a"
                        "6aabcd58e80ce9df61ccf13885ebd714595df69709f09722ff41eb"
                        "37ea5b06f727b7fab01c94588459ccf13885ebd714595df69709f0"
                        "9722ff32b544a259d2fa6e7ddaac1fdff91bb0"
                    )
                },
            }
        ),
    )
    cloud_client.authenticate()
    cloud_client._security.access_token = (
        "87836529d24810fb715db61f2d3eba2ab920ebb829d567559397ded751813801"  # noqa: E501
    )
    result = cloud_client.appliance_transparent_send(str(12345), b"\x12\x34\x81")
    assert len(result) == 1
    assert (
        result[0].hex()
        == "412100ff030000020000000000000000000000000b24a400000000000000000000000000000000"  # noqa: E501
    )
