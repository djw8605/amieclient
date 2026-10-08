import json

from math import ceil, floor

import requests

from .packet import PacketList
from .packet.base import Packet
from .transaction import Transaction
from .usage import (UsageMessage, UsageRecord, UsageResponse, UsageResponseError,
                    FailedUsageResponse, UsageStatus, UsageLoaded)


"""AMIE client and Usage Client classes"""


class AMIERequestError(requests.RequestException):
    pass


class AMIEClient(object):
    """
    AMIE Client.

    Args:
        site_name (str): Name of the client site.
        api_key (str): API key secret
        amie_url (str): Base URL for the XSEDE AMIE api

    Examples:
        >>> psc_client = amieclient.AMIEClient(site_name='PSC', api_key=some_secrets_store['amie_api_key'])

        You can also override the amie_url and usage_url parameters, if you're
        doing local development or testing out a new version.

        >>> psc_alt_base_client = amieclient.AMIEClient(site_name='PSC', api_key='test_api_key', amie_url='https://amieclient.xsede.org/v0.20_beta/)

    """
    def __init__(self, site_name, api_key,
                 amie_url='https://amieclient.xsede.org/v0.10/'):
        if not amie_url.endswith('/'):
            self.amie_url = amie_url + '/'
        else:
            self.amie_url = amie_url

        self.site_name = site_name

        amie_headers = {
            'XA-API-KEY': api_key,
            'XA-SITE': site_name
        }
        s = requests.Session()
        s.headers.update(amie_headers)
        self._session = s

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._session.close()

    @staticmethod
    def _join_list(things):
        if things is not None and things != []:
            # If we're given a list, join it with commas
            return ','.join(things)
        elif things == []:
            # if we're given an empty list, return None
            return None
        else:
            # If we're given anything else, i.e. None or some other single
            # thing, give it back
            return things

    @staticmethod
    def _dt_range(start, end):
        if start is None and end is None:
            time_str = None
        else:
            start_str = start.isoformat() if start else ""
            end_str = end.isoformat() if end else ""
            time_str = "{},{}".format(start_str, end_str)
        return time_str

    def get_transaction(self, transaction_or_id):
        """
        Given a single transaction record id, fetches the related transaction.

        See the :swagger:`Swagger documentation <AMIE_Client/get_transactions__site_name___amie_transaction_id__packets/>` for more details.

        Args:
            transaction_or_id: The transaction or transaction record ID.

        Returns:
            amieclient.Transaction
        """
        if isinstance(transaction_or_id, Transaction):
            tx_id = transaction_or_id.trans_rec_id
        else:
            tx_id = transaction_or_id

        url = self.amie_url + 'transactions/{}/{}/packets'.format(self.site_name, tx_id)
        r = self._session.get(url)
        response = r.json()
        print(response)
        if r.status_code > 200:
            message = response.get('message', 'Server did not provide an error message')
            raise AMIERequestError(message, response=r)
        return Transaction.from_dict(response['result'])

    def set_transaction_failed(self, transaction_or_id):
        """
        Given a single transaction or transaction record id, marks it faield.

        See the :swagger:`Swagger documentation <AMIE_Client/put_transactions__site_name___amie_transaction_id__state_failed>` for more details.

        Args:
            transaction_or_id: The transaction or transaction record ID.
        """
        if isinstance(transaction_or_id, Transaction):
            tx_id = transaction_or_id.trans_rec_id
        else:
            tx_id = transaction_or_id

        url = self.amie_url + 'transactions/{}/{}/state/failed'.format(self.site_name, tx_id)
        r = self._session.put(url)
        response = r.json()
        if r.status_code > 200:
            message = response.get('message', 'Server did not provide an error message')
            raise AMIERequestError(message, response=r)
        return r


    def get_packet(self, packet_rec_id):
        """
        Given a single packet record id, fetches the packet.

        See the :swagger:`Swagger documentation <AMIE_Client/get_packets__site_name_>` for more details.

        Args:
            packet_rec_id: The transaction record ID.

        Returns:
            amieclient.Packet
        """
        url = self.amie_url + 'packets/{}/{}'.format(self.site_name, packet_rec_id)
        r = self._session.get(url)
        response = r.json()
        if r.status_code > 200:
            message = response.get('message', 'Server did not provide an error message')
            raise AMIERequestError(message, response=r)
        return Packet.from_dict(response['result'])

    def list_packets(self, *, trans_rec_ids=None, outgoing=None,
                     update_time_start=None, update_time_until=None,
                     states=None, client_states=None, transaction_states=None,
                     incoming=None):
        """
        Fetches a list of packets based on the provided search parameters

        See the :swagger:`Swagger documentation <AMIE_Client/get_packets__site_name_>` for more details.

        Args:
            trans_rec_ids (list): Searches for packets with these transaction record  IDs.
            states (list): Searches for packets with the provided states.
            update_time_start (datetime.Datetime): Searches for packets updated since this time.
            update_time_until (datetime.Datetime): Searches for packets updated before this time.
            states (list): Searches for packets in the provided states.
            client_states (list): Searches for packets in the provided client states.
            transaction_states (list): Searches for packets in the provided client states.
            incoming (bool): If true, search is limited to incoming packets.

        Returns:
            amieclient.PacketList: a list of packets matching the provided parameters.
        """
        trans_rec_ids_str = self._join_list(trans_rec_ids)
        states_str = self._join_list(states)
        client_states_str = self._join_list(client_states)
        transaction_states_str = self._join_list(transaction_states)
        time_str = self._dt_range(update_time_start, update_time_until)

        # Build a dict of parameters. Requests skips any with a None value,
        # so no need to weed them out
        params = {
            'trans_rec_id': trans_rec_ids_str,
            'outgoing': outgoing,
            'update_time': time_str,
            'states': states_str,
            'client_state': client_states_str,
            'transaction_state': transaction_states_str,
            'incoming': incoming
        }

        # Get the list of packets
        url = self.amie_url + 'packets/{}'.format(self.site_name)
        r = self._session.get(url, params=params)
        response = r.json()
        if r.status_code > 200:
            message = response.get('message', 'Server did not provide an error message')
            raise AMIERequestError(message, response=r)
        return PacketList.from_dict(response)

    def send_packet(self, packet, skip_validation=False):
        """
        Send a packet

        See the :swagger:`Swagger documentation <AMIE_Client/post_packets__site_name_>` for more details.

        Args:
            packet (amieclient.Packet): The packet to send.

        Returns:
            requests.Response: The response from the AMIE API.
        """
        if not skip_validation:
            packet.validate_data(raise_on_invalid=True)

        url = self.amie_url + 'packets/{}'.format(self.site_name)
        r = self._session.post(url, json=packet.as_dict())
        response = r.json()
        if r.status_code > 200:
            message = response.get('message', 'Server did not provide an error message')
            raise AMIERequestError(message, response=r)
        return r

    def set_packet_client_state(self, packet_or_id, state):
        """
        Set the client state on the server of the packet corresponding to the given
        packet_or_id.

        See the :swagger:`Swagger documentation <AMIE_Client/put_packets__site_name___packet_rec_id__client_state__client_state_>` for more details.

        Args:
          packet_or_id (Packet, int): The packet or packet_rec_id to set state on.
          state (str): The state to set
        """
        if isinstance(packet_or_id, Packet):
            pkt_id = packet_or_id.packet_rec_id
        else:
            pkt_id = packet_or_id

        url = self.amie_url + 'packets/{}/{}/client_state/{}'.format(self.site_name,
                                                                     pkt_id, state)

        r = self._session.put(url)
        response = r.json()
        if r.status_code > 200:
            message = response.get('message', 'Server did not provide an error message')
            raise AMIERequestError(message, response=r)
        return r

    def clear_packet_client_state(self, packet_or_id):
        """
        Clears the client state on the server of the packet corresponding to the given
        packet_or_id.

        See the :swagger:`Swagger documentation <AMIE_Client/delete_packets__site_name___packet_rec_id__client_state_>` for more details.

        Args:
          packet_or_id (Packet, int): The packet or packet_rec_id to clear client_state on.
        """
        if isinstance(packet_or_id, Packet):
            pkt_id = packet_or_id.packet_rec_id
        else:
            pkt_id = packet_or_id

        url = self.amie_url + 'packets/{}/{}/client_state'.format(self.site_name, pkt_id)

        r = self._session.delete(url)
        response = r.json()
        if r.status_code > 200:
            message = response.get('message', 'Server did not provide an error message')
            raise AMIERequestError(message, response=r)
        return r

    def set_packet_client_json(self, packet_or_id, client_json):
        """
        Set the client JSON on the server of the packet corresponding to the given
        packet_or_id.

        See the :swagger:`Swagger documentation <AMIE_Client/put_packets__site_name___packet_rec_id__client_json>` for more details.

        Args:
          packet_or_id (Packet, int): The packet or packet_rec_id to set client_json on.
          client_json: The json to set. Can be any serializable object or a string of
            JSON.
        """
        if isinstance(packet_or_id, Packet):
            pkt_id = packet_or_id.packet_rec_id
        else:
            pkt_id = packet_or_id

        url = self.amie_url + 'packets/{}/{}/client_json'.format(self.site_name, pkt_id)

        if isinstance(client_json, str):
            # Best to parse the json here. Ensures it's valid and that everything
            # serializes back properly when we do the PUT
            client_json = json.loads(client_json)

        r = self._session.put(url, json=client_json)
        response = r.json()
        if r.status_code > 200:
            message = response.get('message', 'Server did not provide an error message')
            raise AMIERequestError(message, response=r)
        return r

    def clear_packet_client_json(self, packet_or_id):
        """
        Clears the client JSON on the server of the packet corresponding to the given
        packet_or_id.

        See the :swagger:`Swagger documentation <AMIE_Client/delete_packets__site_name___packet_rec_id__client_json>` for more details.

        Args:
          packet_or_id (Packet, int): The packet or packet_rec_id to clear client_json on.
        """
        if isinstance(packet_or_id, Packet):
            pkt_id = packet_or_id.packet_rec_id
        else:
            pkt_id = packet_or_id

        url = self.amie_url + 'packets/{}/{}/client_json'.format(self.site_name, pkt_id)

        r = self._session.delete(url)
        response = r.json()
        if r.status_code > 200:
            message = response.get('message', 'Server did not provide an error message')
            raise AMIERequestError(message, response=r)
        return r


class UsageClient:
    """
    AMIE Usage Client.

    Args:
        site_name (str): Name of the client site.
        api_key (str): API key secret
        usage_url (str): Base URL for the ACCESS Usage api

    Examples:
        >>> psc_client = amieclient.UsageClient(site_name='PSC', api_key=some_secrets_store['amie_api_key'])

        You can also override the amie_url and usage_url parameters, if you're
        doing local development or testing out a new version.

        >>> psc_alt_base_client = amieclient.UsageClient(site_name='PSC', api_key='test_api_key', usage_url='https://amieclient.xsede.org/v0.20_beta/)

    """
    # The Usage API User's Guide limits a POST to 256 KB; stay well under it.
    MAX_POST_BYTES = 196608

    def __init__(self, site_name, api_key,
                 usage_url='https://usage.access-ci.org/api/v1'):

        if not usage_url.endswith('/'):
            self.usage_url = usage_url + '/'
        else:
            self.usage_url = usage_url

        self.site_name = site_name

        amie_headers = {
            'XA-API-KEY': api_key,
            'XA-SITE': site_name
        }
        s = requests.Session()
        s.headers.update(amie_headers)
        self._session = s

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._session.close()

    def send(self, usage_packets):
        """
        Sends a usage update to the Usage API host. This function accepts
        individual UsageMessages, lists of UsageRecords, or even a single
        UsageRecord. Returns a list of UsageResponses

        The Usage API User's Guide limits a POST to 256 KB. We leave room
        for overhead that may be added by intermediate layers (reverse
        proxies, etc) by capping the size of the request we send to 192KiB.
        This happens automatically, no need to chunk your usage packets
        yourself. But this potential chunking means that we may get more
        than one response, so for the sake of consistency this method will
        return a list of responses.

        Args:
            usage_packets (UsageMessage, [UsageRecord], UsageRecord):
                A UsageMessage object, list of UsageRecords, or a single
                UsageRecord to send.
        Returns:
            list of responses
        """
        if isinstance(usage_packets, UsageRecord):
            pkt_list = UsageMessage([usage_packets])
        elif isinstance(usage_packets, list):
            pkt_list = UsageMessage(usage_packets)
        elif isinstance(usage_packets, UsageMessage):
            pkt_list = usage_packets
        url = self.usage_url + 'usage/'

        # prepare the request
        req = requests.Request('POST',  url, json=pkt_list.as_dict())
        prepped_req = self._session.prepare_request(req)
        # Get the size of the content
        content_length = int(prepped_req.headers.get('Content-Length'))

        # Cap content_length at MAX_POST_BYTES. A single record can't be
        # split any further, so send it as-is.
        if content_length >= self.MAX_POST_BYTES and len(pkt_list.records) > 1:
            # Get the safe number of safe chunks:
            number_of_chunks = ceil(content_length / self.MAX_POST_BYTES)
            # Get the size of those chunks
            chunk_size = max(1, floor(len(pkt_list.records) / number_of_chunks))
            results = list()
            for chunk in pkt_list._chunked(chunk_size=chunk_size):
                # Send each chunk
                r = self.send(chunk)
                results.extend(r)
            return results

        r = self._session.send(prepped_req)
        if r.status_code == 200:
            resp = UsageResponse.from_dict(r.json())
        elif r.status_code == 400:
            # Get the message if we're given one; otherwise
            msg = r.json().get('error', 'Bad Request, but error not specified by server')
            raise UsageResponseError(msg)
        else:
            r.raise_for_status()
        return [resp]

    def summary(self):
        """
        Gets a usage summary

        Not implemented yet
        """
        raise NotImplementedError("Usage summaries are not yet implemented in the AMIE Usage api")

    def get_failed_records(self):
        """
        Gets all failed records

        Takes no arguments
        """

        url = self.usage_url + 'usage/failed'
        r = self._session.get(url)

        if r.status_code > 200:
            # Get the message if we're given one; otherwise placeholder
            msg = r.json().get('error', 'Bad Request, but error not specified by server')
            raise UsageResponseError(msg)
        return FailedUsageResponse.from_dict(r.json())

    def clear_failed_records(self, failed_records_or_ids):
        """
        Tells the server to clear the failed records given

        Args:
            failed_records_or_ids ([FailedUsageRecord], [int]):
                A list of FailedUsageRecords, or plain FailedRecordIds, to unmark as
                failed
        """

        def _get_id(fr):
            if hasattr(fr, 'failed_record_id'):
                return str(fr.failed_record_id)
            else:
                return str(fr)

        if isinstance(failed_records_or_ids, list):
            failed_ids = map(_get_id, failed_records_or_ids)
        else:
            failed_ids = [_get_id(failed_records_or_ids)]

        fids = ','.join(failed_ids)

        url = self.usage_url + 'usage/failed/{}'.format(fids)

        r = self._session.delete(url)
        r.raise_for_status()
        return True

    def status(self, from_time=None, to_time=None):
        """
        Gets the status of records processed from the queue in the provided interval.


        Args:
            from_date (Datetime): Start date and time
            to_date (Datetime): End date and time

        """
        from_iso = from_time.isoformat() if from_time is not None else None
        to_iso = to_time.isoformat() if to_time is not None else None
        p = {'FromTime': from_iso, 'ToTime': to_iso}

        url = self.usage_url + 'usage/status'
        r = self._session.get(url, params=p)
        if r.status_code > 200:
            # Get the message if we're given one; otherwise
            msg = r.json().get('error', 'Bad Request, but error not specified by server')
            raise UsageResponseError(msg)
        return UsageStatus.from_list(r.json())

    def loaded(self, min_loaded_time=None, limit=None, offset=None,
               local_record_id=None):
        """
        Gets records that have been successfully loaded into the accounting
        database. The API returns at most 25,000 records per request, ordered
        by load time; use offset to page through more. The API currently
        only reports Compute usage.

        Args:
            min_loaded_time (Datetime or str): Earliest load time of the
                records returned. The API defaults to one day ago.
            limit (int): Maximum number of records to return
            offset (int): Number of records to skip, for paging
            local_record_id (str): Return only this record. The API ignores
                the other parameters when this is set.
        """
        if min_loaded_time is not None and hasattr(min_loaded_time, 'isoformat'):
            min_loaded_time = min_loaded_time.isoformat()
        p = {
            'MinLoadedTime': min_loaded_time,
            'Limit': limit,
            'Offset': offset,
            'LocalRecordID': local_record_id,
        }

        url = self.usage_url + 'usage/loaded'
        r = self._session.get(url, params=p)
        if r.status_code > 200:
            # Get the message if we're given one; otherwise
            msg = r.json().get('error', 'Bad Request, but error not specified by server')
            raise UsageResponseError(msg)
        return UsageLoaded.from_dict(r.json())
