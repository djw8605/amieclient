from datetime import datetime, timezone

from ..client import UsageClient
from ..usage import (ComputeUsageRecord, FailedUsageResponse, UsageLoaded,
                     UsageLoadedRecord, UsageStatus)

USAGE_URL = 'https://usage.access-ci.org/api/v1/'


def _compute_record(local_record_id='123456', **kwargs):
    fields = dict(
        username='light',
        local_project_id='pscstaff',
        local_record_id=local_record_id,
        resource='bridges.psc.xsede',
        submit_time='2020-09-10T22:06:16Z',
        start_time='2020-09-10T22:06:16Z',
        end_time='2020-09-10T23:06:16Z',
        charge='123.45',
        node_count=3,
    )
    fields.update(kwargs)
    return ComputeUsageRecord(**fields)


# The failed and loaded bodies are the examples from the ACCESS Usage API
# User's Guide; their envelopes match what the live API returns. The live
# usage/status endpoint returns a bare list of resources.
STATUS_JSON = [
    {
        'Resource': 'bridges.psc.xsede',
        'LoadedRecordCount': 1,
        'FailedJobCount': 0,
        'TotalCharge': 3233.12,
        'Errors': []
    }
]

FAILED_JSON = {
    'FailedRecords': [
        {
            'Charge': 2.52,
            'EndTime': '2020-10-20T22:04:02Z',
            'Resource': 'bridges.psc.xsede',
            'Username': 'sligocki',
            'StartTime': '2020-10-20T21:53:14Z',
            'UsageType': 'Compute',
            'Attributes': {'Queue': 'RM-SHARED', 'NodeCount': 1, 'CpuCoreCount': 14},
            'SubmitTime': '2020-10-20T18:55:01Z',
            'LocalRecordID': '11390517_30',
            'LocalProjectID': 'DEB200005P',
            'ServiceProvider': 'PSC',
            'Error': 'Allocation could not be found for user sligocki project DEB200005P resource bridges.psc.xsede',
            'FailedRecordID': '1108'
        }
    ]
}

LOADED_JSON = {
    'Records': [
        {
            'AccountingDbRecordID': '134919900',
            'LocalRecordID': '1236959',
            'Resource': 'bridges2-rm.psc.xsede.org',
            'SubmitTime': '2021-05-20T18:12:54+00:00',
            'LoadedTime': '2022-06-13T17:04:02+00:00',
            'Charge': 0.044
        },
        {
            'AccountingDbRecordID': '134919901',
            'LocalRecordID': '1236966',
            'Resource': 'bridges2-rm.psc.xsede.org',
            'SubmitTime': '2021-05-20T13:22:56+00:00',
            'LoadedTime': '2022-06-13T17:04:02+00:00',
            'Charge': 0.04
        }
    ]
}


class TestComputeUsageRecord:

    def test_parent_record_id_omitted_when_not_given(self):
        d = _compute_record().as_dict()
        assert 'ParentRecordID' not in d

    def test_parent_record_id_is_a_plain_value(self):
        d = _compute_record(parent_record_id='123000').as_dict()
        assert d['ParentRecordID'] == '123000'

    def test_round_trip_keeps_parent_record_id(self):
        d = _compute_record(parent_record_id='123000').as_dict()
        d['UsageType'] = 'Compute'
        assert ComputeUsageRecord.from_dict(d).parent_record_id == '123000'


class TestUsageClientDefaults:

    def test_default_usage_url_is_access(self):
        client = UsageClient(site_name='test', api_key='test')
        assert client.usage_url == USAGE_URL


class TestUsageClientSend:

    def test_send_single_record(self, requests_mock):
        requests_mock.post(USAGE_URL + 'usage/', json={
            'Message': '1 records have been queued for loading.  0 records failed validation.',
            'ValidationFailedRecords': []
        })
        client = UsageClient(site_name='test', api_key='test')

        responses = client.send(_compute_record())

        assert len(responses) == 1
        assert responses[0].failed_records == []
        body = requests_mock.last_request.json()
        assert body['UsageType'] == 'Compute'
        assert 'ParentRecordID' not in body['Records'][0]

    def test_send_chunks_oversized_messages(self, requests_mock):
        requests_mock.post(USAGE_URL + 'usage/', json={
            'Message': 'queued',
            'ValidationFailedRecords': []
        })
        client = UsageClient(site_name='test', api_key='test')
        # Each record serializes to a few hundred bytes, so this exceeds the
        # 768KiB cap and has to be split into several POSTs.
        records = [_compute_record(local_record_id=str(i), job_name='x' * 200)
                   for i in range(3000)]

        responses = client.send(records)

        assert requests_mock.call_count > 1
        assert len(responses) == requests_mock.call_count
        sent = sum(len(r.json()['Records']) for r in requests_mock.request_history)
        assert sent == len(records)


class TestUsageClientFailedRecords:

    def test_get_failed_records_parses_failed_records(self, requests_mock):
        requests_mock.get(USAGE_URL + 'usage/failed', json=FAILED_JSON)
        client = UsageClient(site_name='test', api_key='test')

        failed = client.get_failed_records()

        assert isinstance(failed, FailedUsageResponse)
        assert len(failed.failed_records) == 1
        record = failed.failed_records[0]
        assert record.failed_record_id == '1108'
        assert record.error.startswith('Allocation could not be found')
        assert record.record.local_record_id == '11390517_30'


class TestUsageClientStatus:

    def test_status_sends_time_range(self, requests_mock):
        requests_mock.get(USAGE_URL + 'usage/status', json=STATUS_JSON)
        client = UsageClient(site_name='test', api_key='test')

        status = client.status(
            from_time=datetime(2020, 9, 7, tzinfo=timezone.utc),
            to_time=datetime(2020, 9, 14, tzinfo=timezone.utc),
        )

        assert isinstance(status, UsageStatus)
        assert status.resources[0].loaded_record_count == 1
        qs = requests_mock.last_request.qs
        assert qs['fromtime'] == ['2020-09-07t00:00:00+00:00']
        assert qs['totime'] == ['2020-09-14t00:00:00+00:00']

    def test_status_json_round_trip(self, requests_mock):
        requests_mock.get(USAGE_URL + 'usage/status', json=STATUS_JSON)
        client = UsageClient(site_name='test', api_key='test')

        status = client.status()

        assert UsageStatus.from_json(status.json()).as_list() == status.as_list()


class TestUsageClientLoaded:

    def test_loaded_parses_records(self, requests_mock):
        requests_mock.get(USAGE_URL + 'usage/loaded', json=LOADED_JSON)
        client = UsageClient(site_name='test', api_key='test')

        loaded = client.loaded()

        assert isinstance(loaded, UsageLoaded)
        assert len(loaded.records) == 2
        first = loaded.records[0]
        assert isinstance(first, UsageLoadedRecord)
        assert first.accounting_db_record_id == '134919900'
        assert first.local_record_id == '1236959'
        assert first.resource == 'bridges2-rm.psc.xsede.org'
        assert first.submit_time == '2021-05-20T18:12:54+00:00'
        assert first.loaded_time == '2022-06-13T17:04:02+00:00'
        assert first.charge == 0.044
        assert requests_mock.last_request.qs == {}

    def test_loaded_sends_query_parameters(self, requests_mock):
        requests_mock.get(USAGE_URL + 'usage/loaded', json={'Records': []})
        client = UsageClient(site_name='test', api_key='test')

        loaded = client.loaded(
            min_loaded_time=datetime(2022, 6, 13, tzinfo=timezone.utc),
            limit=100,
            offset=200,
        )

        assert loaded.records == []
        qs = requests_mock.last_request.qs
        assert qs['minloadedtime'] == ['2022-06-13t00:00:00+00:00']
        assert qs['limit'] == ['100']
        assert qs['offset'] == ['200']

    def test_loaded_by_local_record_id(self, requests_mock):
        requests_mock.get(USAGE_URL + 'usage/loaded', json={'Records': LOADED_JSON['Records'][:1]})
        client = UsageClient(site_name='test', api_key='test')

        loaded = client.loaded(local_record_id='1236959')

        assert loaded.records[0].local_record_id == '1236959'
        assert requests_mock.last_request.qs == {'localrecordid': ['1236959']}

    def test_loaded_accepts_string_time(self, requests_mock):
        requests_mock.get(USAGE_URL + 'usage/loaded', json={'Records': []})
        client = UsageClient(site_name='test', api_key='test')

        client.loaded(min_loaded_time='2022-06-13T00:00:00Z')

        assert requests_mock.last_request.qs['minloadedtime'] == ['2022-06-13t00:00:00z']

    def test_loaded_json_round_trip(self, requests_mock):
        requests_mock.get(USAGE_URL + 'usage/loaded', json=LOADED_JSON)
        client = UsageClient(site_name='test', api_key='test')

        loaded = client.loaded()

        assert loaded.as_dict() == LOADED_JSON
        assert UsageLoaded.from_json(loaded.json()).as_dict() == LOADED_JSON
