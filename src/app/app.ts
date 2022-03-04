import { Socket } from "dgram";
import { argv } from "process";
import { finished } from "stream";

var fs = require('fs');
var net = require('net');

function agent(agent_dir : string) {
    console.log("Working as agent");
    var monitored_filename;
    var hostport;

    // const agent_dir = "agent/";
    fs.promises.readFile(agent_dir + "/outputs.json")
    .then(function(data) {
        var json = JSON.parse(data);
        hostport = json.tcp;
        console.log("tcp=", hostport);

        return fs.promises.readFile(agent_dir + "/inputs.json")
    })
    .then(function (data) {
        var json = JSON.parse(data);
        monitored_filename = agent_dir + "/" + json.monitor;
        console.log("monitored_filename=", monitored_filename);

        console.log("Connecting to ", hostport);
        var clientSocket = net.createConnection({host: hostport.host, port: hostport.port}, function () {
            console.log("connected to target", hostport);

            const rs = fs.createReadStream(monitored_filename);
            rs.pipe(clientSocket);

        });
    
    })
    .catch(function(error) {
        console.log(error);
    });
}

function writeToSocket(data, remoteSocket, localSocket) {
    var flushed = remoteSocket.write(data);
    if (!flushed) {
        // We could not write to one of the targets
        localSocket.pause();
    }
}

function splitter(conf_directory) {
    console.log("working as splitter");

    var data = fs.readFileSync(conf_directory + "/outputs.json");
    var json = JSON.parse(data);
    var targets = json.tcp;
    console.log("targets", targets)
    var sockIdx = 0;

    var data = fs.readFileSync(conf_directory + "/inputs.json");
    var json = JSON.parse(data);
    const port = json.tcp;
    const server = net.createServer( (localSocket) => {
        console.log("client connected");

        var outSocks = [];
        targets.forEach(target => {
            console.log('processing ', target)
            var sock = net.createConnection( target, () => {
                console.log("Connected to ", target);
            });
            sock.on('end', ()=> {
                console.error('Disconnected', target);
            });
            outSocks.push(sock);

            sock.on('drain', ()=> {
                localSocket.resume();
            })
        });

        localSocket.on('data', (data)=>{
            // find new line if it exists. 
            //      Send 1st part to current socket (sockIdx)
            //      Send 2nd part to next socket(socket2). Make socket2 the current socket
            // If no new line exists, send to the current socket
            var idx = data.indexOf("\n");
            var part_1 = "";
            var part_2 = "";

            if (idx == -1) {
                part_1 = data;
                writeToSocket(part_1, outSocks[sockIdx], localSocket);
            } else {
                part_1 = data.slice(0, idx + 1); /* include the line termination */
                part_2 = data.slice(idx + 1);

                writeToSocket(part_1, outSocks[sockIdx], localSocket); sockIdx++; sockIdx %= outSocks.length;
                writeToSocket(part_2, outSocks[sockIdx], localSocket);
            }
        });
    });

    server.listen(port, ()=> {
        console.log("App listening on port", port);
    });
}

function target(conf_directory) {
    console.log("working as target");

    var data = fs.readFileSync(conf_directory + "/outputs.json");
    var json = JSON.parse(data);
    var outputfile = json.file;
    console.log("outputfile", outputfile)

    var data = fs.readFileSync(conf_directory + "/inputs.json");
    var json = JSON.parse(data);
    const port = json.tcp;
    const server = net.createServer( (localSocket) => {
        console.log("client connected");
        localSocket.on('data', (data)=>{
            fs.appendFile(outputfile, data, ()=> {
                // written to file
                // console.debug("Written to file");
            })
        });
    });

    server.listen(port, ()=> {
        console.log("App listening on port", port);
    });
}

// For debugging
const os = require('os');
console.log("My hostname is: " + os.hostname());

if (process.argv.length != 3) {
    console.error("Usage: " + process.argv0 + " " + process.argv[1] + " <config_dir>");
    process.exit(1);
}

const conf_directory = process.argv[2]
if (!fs.existsSync(conf_directory)) {
    console.error("Make sure directory '" + conf_directory + "' exists");
    process.exit(1);
}

try {
    const data = fs.readFileSync(conf_directory + "/app.json")
    const json = JSON.parse(data);
    switch (json.mode) {
        case 'agent':
            agent(conf_directory);
            break;
        case 'splitter':
            splitter(conf_directory);
            break;
        case 'target':
            target(conf_directory);
            break;
        default:
            console.log("Usage: ", process.argv[0], process.argv[1], "agent|splitter|target");
            console.warn("Cannot understand app argument", process.argv);
            process.exit(1);
    }
} catch (err) {
    console.log("Usage: ", process.argv[0], process.argv[1], "agent|splitter|target");
    console.error("Encountered error", err);
}
