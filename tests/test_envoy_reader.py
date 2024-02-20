"""Tests for envoy_reader."""
import json
import logging
from pathlib import Path
from os import listdir
from os.path import isfile, join
from typing import Any

from unittest.mock import patch
import pytest
import respx
from httpx import Response
from syrupy.assertion import SnapshotAssertion

from custom_components.enphase_envoy_custom.envoy_reader import EnvoyReader


LOGGER = logging.getLogger(__name__)
#LOGGER.setLevel(logging.DEBUG)
#logging.getLogger("custom_components.enphase_envoy_custom.envoy_reader").setLevel(LOGGER.level)


def _fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"

def _load_fixture(version: str, name: str) -> str:
    with open(_fixtures_dir() / version / name) as read_in:
        return read_in.read()

def _load_json_fixture(version:str, name: str):
    with open(_fixtures_dir() / version / name, "r") as read_in:
        return json.load(read_in)

def _add_file_mock(version: str, url_path: str, files: list[str], use_file: str = "") -> None:
    file = url_path[1:].replace("/","_") if use_file == "" else use_file
    if file in files:
        try:
            json_data = _load_json_fixture(version, file)
        except json.decoder.JSONDecodeError:
            json_data = None
        respx.get(url_path).mock(return_value=Response(200, json=json_data))
    else:
        respx.get(url_path).mock(return_value=Response(404))


def _start_7_firmware_mock(version: str):
    """Start the firmware 7 mock."""
    path = f"{_fixtures_dir()}/{version}"
    files = [f for f in listdir(path) if isfile(join(path, f))]
    print(files)
    respx.post("https://enlighten.enphaseenergy.com/login/login.json?").mock(
        return_value=Response(
            200,
            json={
                "session_id": "1234567890",
                "user_id": "1234567890",
                "user_name": "test",
                "first_name": "Test",
                "is_consumer": True,
                "manager_token": "1234567890",
            },
        )
    )
    respx.post("https://entrez.enphaseenergy.com/tokens").mock(
        return_value=Response(200, text="token")
    )
    respx.get("/auth/check_jwt").mock(return_value=Response(200, json={}))
    respx.get("/info").mock(
        return_value=Response(200, text=_load_fixture(version, "info"))
    )
    respx.get("/info.xml").mock(return_value=Response(200, text=""))

    _add_file_mock(version,"/home",files=files)
    _add_file_mock(version,"/production",files=files)
    _add_file_mock(version,"/production.json",files=files)
    _add_file_mock(version,"/api/v1/production",files=files)
    _add_file_mock(version,"/api/v1/production/inverters",files=files)
    _add_file_mock(version,"/ivp/ensemble/inventory",files=files)
    _add_file_mock(version,"/home.json",files=files)
    _add_file_mock(version,"/ivp/meters",files=files)
    _add_file_mock(version,"/ivp/meters/reports",files=files)
    _add_file_mock(version,"/ivp/meters/readings",files=files)

async def _get_envoy_reader(do_not_use_production_json: bool = False) -> EnvoyReader:
    reader : EnvoyReader = EnvoyReader(
        host="127.0.0.1",
        username="test-user",
        password = "test-password",
        enlighten_user="test-user",
        enlighten_pass="test-password",
        inverters=True,
        use_enlighten_owner_token=True,
        enlighten_serial_num="123456789012",
        https_flag='s',
        do_not_use_production_json=do_not_use_production_json,
    )
    return reader

async def _envoy_dataset(reader: EnvoyReader) -> dict[str,Any]:
    """Pack envoy data in dict."""
    dataset: dict[str,Any] = {}

    dataset["endpoint_type"] = reader.endpoint_type
    dataset["consumption_meters_phase_count"] = reader.consumption_meters_phase_count
    dataset["get_inverters"] = reader.get_inverters
    dataset["has_grid_status"] = reader.has_grid_status
    dataset["https_flag"] = reader.https_flag
    dataset["isConsumptionMeteringEnabled"] = reader.isConsumptionMeteringEnabled
    dataset["isProductionMeteringEnabled"] = reader.isProductionMeteringEnabled
    dataset["net_consumption_meters_type"] = reader.net_consumption_meters_type
    dataset["production_meters_phase_count"] = reader.production_meters_phase_count
    dataset["active_inverter_count"] = await reader.active_inverter_count()
    dataset["inverters_production"] = await reader.inverters_production()

    dataset["production"] = await reader.production()
    dataset["daily_production"] = await reader.daily_production()
    dataset["seven_days_production"] = await reader.seven_days_production()
    dataset["lifetime_production"] = await reader.lifetime_production()

    dataset["consumption"] = await reader.consumption()
    dataset["daily_consumption"] = await reader.daily_consumption()
    dataset["seven_days_consumption"] = await reader.seven_days_consumption()
    dataset["lifetime_consumption"] = await reader.lifetime_consumption()

    dataset["battery_storage"] = await reader.battery_storage()

    dataset["net_consumption"] = await reader.net_consumption()
    dataset["lifetime_net_production"] = await reader.lifetime_net_production()
    dataset["lifetime_net_consumption"] = await reader.lifetime_net_consumption()
    dataset["pf"] = await reader.pf()
    dataset["voltage"] = await reader.voltage()
    dataset["frequency"] = await reader.frequency()
    dataset["consumption_Current"] = await reader.consumption_Current()
    dataset["consumption_Current"] = await reader.consumption_Current()

    dataset["grid_status"] = await reader.grid_status()

    # phase data
    for phase in ['l1','l2','l3']:
        dataset[f"production_phase {phase}"] = await reader.production_phase(phase)
        dataset[f"daily_production_phase {phase}"] = await reader.daily_production_phase(phase)
        dataset[f"lifetime_production_phase {phase}"] = await reader.lifetime_production_phase(phase)
        dataset[f"consumption {phase}"] = await reader.consumption(phase)
        dataset[f"daily_consumption_phase {phase}"] = await reader.daily_consumption_phase(phase)
        dataset[f"lifetime_consumption {phase}"] = await reader.lifetime_consumption(phase)
        dataset[f"net_consumption {phase}"] = await reader.net_consumption(phase)
        dataset[f"lifetime_net_production {phase}"] = await reader.lifetime_net_production(phase)
        dataset[f"lifetime_net_consumption {phase}"] = await reader.lifetime_net_consumption(phase)
        dataset[f"pf {phase}"] = await reader.pf(phase)
        dataset[f"voltage {phase}"] = await reader.voltage(phase)
        dataset[f"frequency {phase}"] = await reader.frequency(phase)
        dataset[f"frequency {phase}"] = await reader.frequency(phase)
        dataset[f"production_Current {phase}"] = await reader.production_Current(phase)

    return dataset

@pytest.mark.asyncio
@respx.mock
async def test_with_3_7_0_firmware( snapshot: SnapshotAssertion):
    """Verify with 3.7.0 firmware."""
    version = "3.7.0"
    respx.get("/info").mock(
        return_value=Response(200, text=_load_fixture(version, "info"))
    )
    respx.get("/info.xml").mock(return_value=Response(200, text=""))
    respx.get("/production").mock(
        return_value=Response(200, text=_load_fixture(version, "production"))
    )
    respx.get("/home").mock(
        return_value=Response(200, text=_load_fixture(version, "home"))        
    )
    respx.get("/production.json").mock(return_value=Response(404))
    respx.get("/api/v1/production").mock(return_value=Response(404))
    respx.get("/api/v1/production/inverters").mock(return_value=Response(404))
    respx.get("/ivp/ensemble/inventory").mock(return_value=Response(404))
    respx.get("/home.json").mock(return_value=Response(404))
    respx.get("/ivp/meters").mock(return_value=Response(404))
    respx.get("/ivp/meters/reports").mock(return_value=Response(404))
    respx.get("/ivp/meters/readings").mock(return_value=Response(404))

    reader = EnvoyReader("127.0.0.1")
    await reader.getData()
    await reader.getData()
    
    result = await _envoy_dataset(reader)
    assert result == snapshot

@pytest.mark.asyncio
@respx.mock
async def test_with_3_9_36_firmware( snapshot: SnapshotAssertion):
    """Verify with 3.9.36 firmware."""
    version = "3.9.36"
    respx.get("/info").mock(
        return_value=Response(200, text=_load_fixture(version, "info"))
    )
    respx.get("/info.xml").mock(return_value=Response(200, text=""))
    respx.get("/production").mock(
        return_value=Response(200, text=_load_fixture(version, "production"))
    )
    respx.get("/home").mock(
        return_value=Response(200, text=_load_fixture(version, "home"))        
    )
    respx.get("/api/v1/production").mock(
        return_value=Response(200, text=_load_fixture(version, "api_v1_production"))        
    )

    respx.get("/api/v1/production/inverters").mock(return_value=Response(404))
    respx.get("/ivp/ensemble/inventory").mock(return_value=Response(404))
    respx.get("/home.json").mock(return_value=Response(404))
    respx.get("/ivp/meters").mock(return_value=Response(404))
    respx.get("/ivp/meters/reports").mock(return_value=Response(404))
    respx.get("/ivp/meters/readings").mock(return_value=Response(404))
    respx.get("/production.json").mock(return_value=Response(404))

    reader = EnvoyReader("127.0.0.1")
    await reader.getData()
    await reader.getData()
    
    result = await _envoy_dataset(reader)
    assert result == snapshot


@pytest.mark.asyncio
@respx.mock
async def test_with_4_2_27_firmware(snapshot: SnapshotAssertion):
    """Verify with 4.2.27 firmware."""
    version = "4.2.27"
    respx.get("/info").mock(
        return_value=Response(200, text=_load_fixture(version, "info"))
    )
    respx.get("/info.xml").mock(return_value=Response(200, text=""))
    respx.get("/production").mock(return_value=Response(404))
    respx.get("/production.json").mock(
        return_value=Response(200, json=_load_json_fixture(version, "production.json"))
    )
    respx.get("/api/v1/production").mock(
        return_value=Response(
            200, json=_load_json_fixture(version, "api_v1_production")
        )
    )
    respx.get("/api/v1/production/inverters").mock(return_value=Response(404, text="[]"))
    respx.get("/ivp/ensemble/inventory").mock(return_value=Response(404))
    respx.get("/home.json").mock(return_value=Response(404))
    respx.get("/ivp/meters").mock(return_value=Response(404))
    respx.get("/ivp/meters/reports").mock(return_value=Response(404))
    respx.get("/ivp/meters/readings").mock(return_value=Response(404))
    
    reader = EnvoyReader("127.0.0.1")
    await reader.getData()
    await reader.getData()
    
    result = await _envoy_dataset(reader)
    assert result == snapshot


@patch('custom_components.enphase_envoy_custom.envoy_reader.EnvoyReader._is_enphase_token_expired', return_value=False)
@pytest.mark.asyncio
@respx.mock
async def test_with_7_6_175_standard(enphase: Any, snapshot: SnapshotAssertion):
    """Test envoy standard."""
    version = "7.6.175-envoy-s-standard"
    _start_7_firmware_mock(version)
    reader: EnvoyReader = await _get_envoy_reader(do_not_use_production_json=False)

    await reader.getData()
    await reader.getData()

    result = await _envoy_dataset(reader)
    assert result == snapshot


@patch('custom_components.enphase_envoy_custom.envoy_reader.EnvoyReader._is_enphase_token_expired', return_value=False)
@pytest.mark.asyncio
@respx.mock
async def test_with_7_6_175_metered(enphase: Any, snapshot: SnapshotAssertion):
    """Test envoy metered."""
    version = "7.6.175-envoy-s-metered"
    _start_7_firmware_mock(version)
    reader: EnvoyReader = await _get_envoy_reader(do_not_use_production_json=False)

    await reader.getData()
    await reader.getData()

    result = await _envoy_dataset(reader)
    assert result == snapshot        


@patch('custom_components.enphase_envoy_custom.envoy_reader.EnvoyReader._is_enphase_token_expired', return_value=False)
@pytest.mark.asyncio
@respx.mock
async def test_with_7_6_175_metered_multiphase(enphase: Any, snapshot: SnapshotAssertion):
    """Test envoy metered multiphase."""
    version = "7.6.175-envoy-s-metered-multiphase"
    _start_7_firmware_mock(version)
    reader: EnvoyReader = await _get_envoy_reader(do_not_use_production_json=False)

    await reader.getData()
    await reader.getData()

    result = await _envoy_dataset(reader)
    assert result == snapshot


@patch('custom_components.enphase_envoy_custom.envoy_reader.EnvoyReader._is_enphase_token_expired', return_value=False)
@pytest.mark.asyncio
@respx.mock
async def test_with_7_6_175_metered_noct(enphase: Any, snapshot: SnapshotAssertion):
    """Test envoy metered without installed CT."""
    version = "7.6.175-envoy-s-metered-no-ct"
    _start_7_firmware_mock(version)
    reader: EnvoyReader = await _get_envoy_reader(do_not_use_production_json=False)

    await reader.getData()
    await reader.getData()

    result = await _envoy_dataset(reader)
    assert result == snapshot


@patch('custom_components.enphase_envoy_custom.envoy_reader.EnvoyReader._is_enphase_token_expired', return_value=False)
@pytest.mark.asyncio
@respx.mock
async def test_with_7_6_175_metered_noprodjson(enphase: Any, snapshot: SnapshotAssertion):
    """Test envoy metered not using production report."""
    version = "7.6.175-envoy-s-metered"
    _start_7_firmware_mock(version)
    reader: EnvoyReader = await _get_envoy_reader(do_not_use_production_json=True)

    await reader.getData()
    await reader.getData()

    result = await _envoy_dataset(reader)
    assert result == snapshot


@patch('custom_components.enphase_envoy_custom.envoy_reader.EnvoyReader._is_enphase_token_expired', return_value=False)
@pytest.mark.asyncio
@respx.mock
async def test_with_7_6_185_metered_battery(enphase: Any, snapshot: SnapshotAssertion):
    """Test envoy metered with batteries."""
    #logging.getLogger("custom_components.enphase_envoy_custom.envoy_reader").setLevel(logging.DEBUG)
    version = "7.6.185-envoy-metered-battery"
    _start_7_firmware_mock(version)
    reader: EnvoyReader = await _get_envoy_reader(do_not_use_production_json=False)

    await reader.getData()
    await reader.getData()

    result = await _envoy_dataset(reader)
    assert result == snapshot


# these are test statements to use when adding new test scenario
# assert await reader.production() == -5
# assert await reader.daily_production() == 0
# assert await reader.seven_days_production() == 73002
# assert await reader.lifetime_production() == 4351113

# assert await reader.consumption() == 209
# assert await reader.daily_consumption() == 63
# assert await reader.seven_days_consumption() == 19
# assert await reader.lifetime_consumption() == 4074795

# assert await reader.battery_storage() == [{
#     "part_num": "830-01760-r37",
#     "installed": 1695330323,
#     "serial_num": "122249097612",
#     "device_status": ["envoy.global.ok", "prop.done"],
#     "last_rpt_date": 1695769447,
#     "admin_state": 6,
#     "admin_state_str": "ENCHG_STATE_READY",
#     "created_date": 1695330323,
#     "img_load_date": 1695330323,
#     "img_pnum_running": "2.6.5973_rel/22.11",
#     "zigbee_dongle_fw_version": "100F",
#     "bmu_fw_version": "2.1.34",
#     "operating": True,
#     "communicating": True,
#     "sleep_enabled": False,
#     "percentFull": 15,
#     "temperature": 29,
#     "maxCellTemp": 30,
#     "comm_level_sub_ghz": 4,
#     "comm_level_2_4_ghz": 4,
#     "led_status": 17,
#     "dc_switch_off": False,
#     "encharge_rev": 2,
#     "encharge_capacity": 3500,
# }]

# assert await reader.net_consumption() == 522
# assert await reader.lifetime_net_production() == 1125590 
# assert await reader.lifetime_net_consumption() == 2404339
# assert await reader.pf() == 0.41
# assert await reader.voltage() == 712.829
# assert await reader.frequency() == 50.00
# assert await reader.consumption_Current() == 2.060
# assert await reader.production_Current() == 0.656

# assert await reader.grid_status() is None

# assert await reader.production_phase("l2") == 0
# assert await reader.daily_production_phase("l2") == 1454
# assert await reader.lifetime_production_phase("l2") == 1241245

# assert await reader.consumption("l2") == 123
# assert await reader.daily_consumption_phase("l2") == 2154
# assert await reader.lifetime_consumption("l2") == 948057

# assert await reader.net_consumption("l2") == 0
# assert await reader.lifetime_net_production("l2") == 8279
# assert await reader.lifetime_net_consumption("l2") == 0

# assert await reader.pf("l2") == 0.56
# assert await reader.voltage("l2") == 237.95
# assert await reader.frequency("l2") == 50.0
# assert await reader.consumption_Current("l2") == 0.873
# assert await reader.production_Current("l2") == -0.0

# assert await reader.active_inverter_count() == 'Active Inverter count not available for your Envoy device.'
# assert await reader.inverters_production() == {
#     "12345678001": [201,"2023-08-07 15:50:41"],
#     "12345678002": [202,"2023-08-07 15:54:13"],
#     "12345678003": [203,"2023-08-07 15:55:09"],
#     "12345678004": [204,"2023-08-07 15:51:39"],
#     "12345678005": [205,"2023-08-07 15:51:11"]
# }

# assert reader.endpoint_type == 'PC'
# assert reader.consumption_meters_phase_count == 1
# assert reader.get_inverters is True
# assert reader.has_grid_status is False
# assert reader.https_flag == 's'
# assert reader.isConsumptionMeteringEnabled is True
# assert reader.isProductionMeteringEnabled is True
# assert reader.net_consumption_meters_type is True
# assert reader.production_meters_phase_count == 1