/*jshint esversion: 6, node:true */
"use strict";
const jsonSize = require("json-size");
const Cloudant = require('cloudant');
const sleep = require('sleep');

const DependencyFactory = require("./util/dependencyFactory");

const dbName = "iotp-cost-calculator";
const inputFile = require("./jsonconf.json");

const wait_time = 1;

let start_date = new Date().toISOString().replace(/T.+/, '');

let env = DependencyFactory.getEnvironment();
let appClient = DependencyFactory.getIotClient();

var storage;

initializeCloudant(function() {
  appClient.connect();
});

appClient.on("error", function(err) {
  console.log("A wild error appeared! : " + err);
});

appClient.on("connect", function() {
  console.log("Starting iotp-cost-calculator");
  console.log("Start Date: " + start_date);
  console.log("Appclient connected");
  let start = Date.now();
  let qos_levels = [0, 1, 2];

  let sending_times = [10, 100, 1000, 10000, 100000, 1000000];

  appClient.getDataUsage(start_date, new Date().toISOString().replace(/T.+/, '')).then(function(data) {
    let old_data_usage = data.total;
    console.log("Old Usage Level: " + old_data_usage);

    console.log("Input File contains: " + Object.keys(inputFile.sizes).length);
    let inputs = Object.keys(inputFile.sizes);
    console.log("Inputs are: " + inputs);
    for (let key in inputs) {
      console.log("inputs[key] is: " + inputs[key]);
      console.log("Sending messages of size: " + inputs[key]);
      let actualSize = jsonSize(inputs[key]);
      console.log("Actual json size: " + actualSize);
      for (let qos in qos_levels) {
        console.log("Sending messages with qos: " + qos);
        for (let sending_time in sending_times) {
          console.log("Sending " + sending_times[sending_time] + " messages");
          for (let i = 0; i < sending_time; i++) {
            appClient.publishDeviceEvent("SimDevice", "SimDevice", "dataUsageEvent", "json", JSON.stringify(inputs[key]), qos, null);
          }
          console.log("Finished sending messages");
          console.log("Waiting " + wait_time + " seconds before getting reported DataUsage");
          sleep.sleep(wait_time);
          appClient.getDataUsage(start_date, new Date().toISOString().replace(/T.+/, '')).then(function(data) {
            console.log("Data Usage information:\n" + JSON.stringify(data));
            let information = {
              "old_data_usage": old_data_usage,
              "reported_data_usage": data.total,
              "delta_data_usage": data.total - old_data_usage,
              "assumpted_delta_data_usage": sending_time * actualSize - old_data_usage,
              "sending_time": sending_time,
              "qos": qos,
              "actualSize": actualSize
            };
            let docId = new Date().toISOString().replace(/\..+/, '');
            console.log("Storing data under id " + docId);
            storage.insert(data, docId, function(err, body) {
              if (!err)
                console.log("Successfully stored information:\n" + JSON.stringify(body));
            });
          });
        }
      }
    }
    let end = Date.now();
    console.log("Sending the messages took " + ((end - start) / 1000) + " seconds");
    appClient.disconnect();
    console.log("Appclient disconnected");
    console.log("App run finished");
  });

});

/**
 */
function initializeCloudant(callback) {
  let credentials = DependencyFactory.getCredentials("cloudantNoSQLDB");
  let cloudant = Cloudant({
    url: credentials.url
  });
  cloudant.db.create(dbName, function(err, data) {
    if (err) { //If database already exists
      console.log("Database exists.");
    } else {
      console.log("Created database.");
    }
  });
  storage = cloudant.db.use(dbName);
  storage.list(function(err, body) {
    if (!err) {
      console.log("Cloudant contains " + body.rows.length + " documents.");
      callback(storage);

    }
  });
}
