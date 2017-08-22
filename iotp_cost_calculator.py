from cloudant import Cloudant
import atexit
import os
import json
import time
import ibmiotf.application
import ibmiotf.api
import sys
import uuid

db_name = 'iotp-cost-calculator'
client = None
db = None

device_type = "SimDevice"
device_id = "SimDevice"

wait_time = 1

# Set today
start_date = time.strftime("%Y-%m-%d")
print "Start Date is {}".format(start_date)


# Env Setup
if 'VCAP_SERVICES' in os.environ:
    vcap = json.loads(os.getenv('VCAP_SERVICES'))
    print('Found VCAP_SERVICES')
    print('This means cloud foundry. Setting wait_time to 7200')
    wait_time = 7200
elif os.path.isfile('vcap-local.json'):
    with open('vcap-local.json') as f:
        vcap = json.load(f)
        print('Found local VCAP_SERVICES')
        print('This means dev env. Setting wait_time to 1')
else:
    sys.exit("No vcap found")

# cloudant setup
if 'cloudantNoSQLDB' in vcap:
    creds = vcap['cloudantNoSQLDB'][0]['credentials']
    user = creds['username']
    password = creds['password']
    url = 'https://' + creds['host']
    client = Cloudant(user, password, url=url, connect=True)
    db = client[db_name]
    if db.exists():
        print("Successfully connected to database {}".format(db_name))
    else:
        db = client.create_database(db_name, throw_on_exists=True)
        print("Successfully created database {}".format(db_name))
    print("Database contains {} documents".format(db.doc_count()))
else:
    sys.exit("No cloudantNoSQLDB in vcap found")

# Load input jsons
if os.path.isfile('jsonconf.json'):
    with open('jsonconf.json') as f:
        jsonconf = json.load(f)

#Setup ibmiotf
appClientConfig = {
    "org": vcap['iotf-service'][0]['credentials']['org'],
    "id": str(uuid.uuid4()),
    "auth-method": "apikey",
    "auth-key": vcap['iotf-service'][0]['credentials']['apiKey'],
    "auth-token": vcap['iotf-service'][0]['credentials']['apiToken'],
  }
appClient = ibmiotf.application.Client(appClientConfig)
appClient.connect()
apiClient = ibmiotf.api.ApiClient(appClientConfig)


############################ Calculator Code ###################################
print("Starting iotp-cost-calculator")
qos_levels = [0, 1, 2];
sending_times = [10, 100, 1000, 10000, 100000, 1000000];

loop_breaker = 0

usage_params = {'start': start_date, 'end': time.strftime("%Y-%m-%d")}
old_usage = apiClient.getDataTraffic(usage_params)
print ("Old Usage Traffic: {}".format(old_usage))

print("Input File contains {} JSON Objects".format(len(jsonconf['sizes'])))
for jsoninput in jsonconf['sizes']:
    print("JSON input size is: {}".format(jsoninput))
    actual_size = len(json.dumps(jsonconf['sizes'][jsoninput]).encode('utf-8'))
    print("Calculated size is: {}".format(actual_size))
    for qos in qos_levels:
        print("Messages with QoS: {}".format(qos))
        for sending_time in sending_times:
            print("Sending messages {} times.".format(sending_time))
            for document in db:
                time.sleep(0.3) # Wait so we dont exceed query/s limit
                if document['sending_time'] == sending_time:
                    if document['qos'] == qos:
                        if document['actual_size'] == actual_size:
                            print("Found document containing data for this combination: {}".format(document['_id']))
                            loop_breaker = 1
                            break
            if loop_breaker == 1:
                loop_breaker = 0
                break
            t0 = time.time()
            times_interrupted = 0
            for i in range(0,sending_time):
                if (i+1)%100002 == 0:
                    print("i is {}. Mod is 0. Waiting 10 seconds".format(i))
                    time.sleep(10)
                    times_interrupted+=1
                appClient.publishEvent(device_type, device_id, "calculator-event", "json", jsonconf['sizes'][jsoninput], qos=qos)
            time_took = round(time.time()-t0, 3)-(10*times_interrupted)
            print("Finished sending messages")
            print("Took {} seconds".format(time_took))
            print("Waiting {} seconds before getting reported DataUsage".format(wait_time))
            time.sleep(wait_time)
            usage_params = {'start': start_date, 'end': time.strftime("%Y-%m-%d")}
            new_usage = apiClient.getDataTraffic(usage_params)
            print("Data Usage Information: {}".format(new_usage))
            doc_id = time.asctime( time.localtime(time.time()) ).replace(" ","-")
            information = {"_id": doc_id,"old_data_usage": old_usage['total'],"reported_data_usage": new_usage['total'],"delta_data_usage": new_usage['total'] - old_usage['total'],"assumed_delta_data_usage": sending_time * actual_size,"sending_time": sending_time,"qos": qos,"actual_size": actual_size, "time_took": time_took}
            print("Storing information under doc_id: {}".format(doc_id))
            new_doc = db.create_document(information)
            if new_doc.exists():
                print("Successfully stored information")
            old_usage = new_usage
            print("information: {}".format(information))

appClient.disconnect()
print("App run finished")

@atexit.register
def shutdown():
    if client:
        client.disconnect()
    if appClient:
        appClient.disconnect()
