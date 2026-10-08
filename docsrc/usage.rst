Usage API
==============

The Usage API client
--------------------

To communicate with the AMIE REST Usage API, create a UsageClient object.
You'll need to provide your site name and your API key.

.. autoclass:: amieclient.client.UsageClient
   :members:


Usage Records
-------------
The Usage API currently handles three kinds of resources:
Compute, Storage, and Adjustment. Each resource has a corresponding
Record type.


Compute
,,,,,,,,,
.. autoclass:: amieclient.usage.record.ComputeUsageRecord
   :members:

Storage
,,,,,,,

.. autoclass:: amieclient.usage.record.StorageUsageRecord
  :members:

Adjustment
,,,,,,,,,,

.. autoclass:: amieclient.usage.record.AdjustmentUsageRecord
  :members:

Usage Messages
--------------
Usage Records are sent and received from the Usage API in the form of Usage Messages.
A Usage Message is, essentially, a list of one particular type of Usage Record -- so, for
example, you cannot send a UsageMessage with a record of both Compute and Storage usage.
The send_usage() method of the Usage Client will make a UsageMessage for you automatically 
if you give it a list of UsageRecords of the same kind, or if you give it a single
UsageRecord.

.. autoclass:: amieclient.usage.message.UsageMessage
  :members:

Responses
---------
The Usage API backend processes received records asynchronously. This means that when you
send along a UsageRecord, your data is validated, but not processed immediately. You will
receive a quick response from the API, letting you know how many records were validated
successfully and put on the stack to be processed. Any records that fail validation will be
returned to you, so that you can correct whatever horrible mistake you have inflicted on the API.
You monster.

.. autoclass:: amieclient.usage.response.UsageResponse
   :members:


Checking status
---------------
To see what the current status of your submitted records are, there is the usage_status()
method. It takes two optional paramters -- from_date and to_date -- that define a date and
time range. The response includes a list of resources. For each resource, the number of
successful and failed records is sent. If there are any records that failed processing,
they are sent as well, grouped by the error that occured.

.. autoclass:: amieclient.usage.response.UsageStatus
   :members:

.. autoclass:: amieclient.usage.response.UsageStatusResource
   :members:


Checking loaded records
-----------------------
To confirm that records made it into the accounting database, use the loaded() method.
It takes optional min_loaded_time, limit, offset, and local_record_id parameters. The API
returns at most 25,000 records per request, ordered by load time, so use offset to page
through more. The API currently only reports Compute usage here.

.. autoclass:: amieclient.usage.response.UsageLoaded
   :members:

.. autoclass:: amieclient.usage.response.UsageLoadedRecord
   :members:
