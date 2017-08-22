from cloudant import Cloudant
import atexit
import cf_deployment_tracker
import os
import json
import time
import ibmiotf.application
import ibmiotf.api
import sys
from flask import Flask

# Emit Bluemix deployment event
cf_deployment_tracker.track()

# Start up a fucking webserver so the fucking bluemix wont kill my app
app = Flask(__name__)
port = int(os.getenv('PORT', 8000))
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port, debug=True)

db_name = 'iotp-cost-calculator'
client = None
db = None

device_type = "SimDevice"
device_id = "SimDevice"

wait_time = 7200

# Set today
start_date = time.strftime("%Y-%m-%d")
print "Start Date is {}".format(start_date)


# Env Setup
if 'VCAP_SERVICES' in os.environ:
    vcap = json.loads(os.getenv('VCAP_SERVICES'))
    print('Found VCAP_SERVICES')
elif os.path.isfile('vcap-local.json'):
    with open('vcap-local.json') as f:
        vcap = json.load(f)
        print('Found local VCAP_SERVICES')
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
    "id": "iotp-cost-calculator",
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
            for i in range(0,sending_time):
                appClient.publishEvent(device_type, device_id, "calculator-event", "json", jsonconf['sizes'][jsoninput], qos=qos)
            print("Finished sending messages")
            print("Waiting {} seconds before getting reported DataUsage".format(wait_time))
            time.sleep(wait_time)
            usage_params = {'start': start_date, 'end': time.strftime("%Y-%m-%d")}
            new_usage = apiClient.getDataTraffic(usage_params)
            print("Data Usage Information: {}".format(new_usage))
            doc_id = time.asctime( time.localtime(time.time()) ).replace(" ","-")
            information = {"_id": doc_id,"old_data_usage": old_usage['total'],"reported_data_usage": new_usage['total'],"delta_data_usage": new_usage['total'] - old_usage['total'],"assumpted_delta_data_usage": sending_time * actual_size - old_usage['total'],"sending_time": sending_time,"qos": qos,"actual_size": actual_size}
            print("Storing information under doc_id: {}".format(doc_id))
            db.create_document(information)

appClient.disconnect()
print("App run finished")

@atexit.register
def shutdown():
    if client:
        client.disconnect()
    if appClient:
        appClient.disconnect()
