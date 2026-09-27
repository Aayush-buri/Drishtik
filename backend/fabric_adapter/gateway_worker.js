const { connect, signers } = require('@hyperledger/fabric-gateway');
const grpc = require('@grpc/grpc-js');
const fs = require('fs');
const crypto = require('crypto');
const readline = require('readline');

const endpoint = process.env.FABRIC_PEER_ENDPOINT || 'localhost:7051';
const mspId = process.env.FABRIC_MSP_ID || 'Org1MSP';
const channelName = process.env.FABRIC_CHANNEL_NAME || 'cctvchannel';
const chaincodeName = process.env.FABRIC_CHAINCODE_NAME || 'evidence_anchor';

const certPath = process.env.FABRIC_CLIENT_CERT_PATH;
const keyPath = process.env.FABRIC_CLIENT_KEY_PATH;
const tlsCertPath = process.env.FABRIC_TLS_CERT_PATH;

async function newGrpcConnection() {
    let credentials;
    if (tlsCertPath && fs.existsSync(tlsCertPath)) {
        const tlsRootCert = fs.readFileSync(tlsCertPath);
        credentials = grpc.credentials.createSsl(tlsRootCert);
    } else {
        credentials = grpc.credentials.createInsecure();
    }
    
    const client = new grpc.Client(endpoint, credentials);
    
    return new Promise((resolve, reject) => {
        const deadline = Date.now() + 5000;
        client.waitForReady(deadline, (err) => {
            if (err) {
                reject(err);
            } else {
                resolve(client);
            }
        });
    });
}

function newIdentity() {
    if (!certPath || !fs.existsSync(certPath)) {
        throw new Error('Client certificate not configured or not found');
    }
    const credentials = fs.readFileSync(certPath);
    return { mspId, credentials };
}

function newSigner() {
    if (!keyPath || !fs.existsSync(keyPath)) {
        throw new Error('Client private key not configured or not found');
    }
    const privateKeyPem = fs.readFileSync(keyPath);
    const privateKey = crypto.createPrivateKey(privateKeyPem);
    return signers.newPrivateKeySigner(privateKey);
}

async function start() {
    let client;
    let gateway;
    let network;
    let contract;

    try {
        if (certPath && keyPath) {
            client = await newGrpcConnection();
            gateway = connect({
                client,
                identity: newIdentity(),
                signer: newSigner(),
                evaluateOptions: () => {
                    return { deadline: Date.now() + 5000 };
                },
                endorseOptions: () => {
                    return { deadline: Date.now() + 15000 };
                },
                submitOptions: () => {
                    return { deadline: Date.now() + 5000 };
                },
                commitStatusOptions: () => {
                    return { deadline: Date.now() + 60000 };
                },
            });
            network = gateway.getNetwork(channelName);
            contract = network.getContract(chaincodeName);
        }
    } catch (e) {
        // Will handle errors per request if not initialized
    }

    const rl = readline.createInterface({
        input: process.stdin,
        output: process.stdout,
        terminal: false
    });

    rl.on('line', async (line) => {
        if (!line.trim()) return;
        
        try {
            const req = JSON.parse(line);
            const { id, method, args } = req;
            
            if (method === 'health') {
                if (!certPath || !keyPath) {
                    console.log(JSON.stringify({ id, error: null, result: { status: 'NOT_CONFIGURED', message: 'Cert or Key not provided' } }));
                    return;
                }
                if (!client || !gateway) {
                    try {
                        client = await newGrpcConnection();
                        gateway = connect({
                            client,
                            identity: newIdentity(),
                            signer: newSigner()
                        });
                        network = gateway.getNetwork(channelName);
                        contract = network.getContract(chaincodeName);
                        console.log(JSON.stringify({ id, error: null, result: { status: 'CONNECTED', message: 'Gateway connected' } }));
                    } catch (err) {
                        console.log(JSON.stringify({ id, error: null, result: { status: 'ERROR', message: err.message } }));
                    }
                } else {
                    console.log(JSON.stringify({ id, error: null, result: { status: 'CONNECTED', message: 'Gateway connected' } }));
                }
            } else if (method === 'evaluate' || method === 'submit') {
                if (!contract) {
                    console.log(JSON.stringify({ id, error: 'NOT_CONFIGURED', result: null }));
                    return;
                }
                
                const { transactionName, transactionArgs } = args;
                try {
                    if (method === 'evaluate') {
                        const resultBytes = await contract.evaluateTransaction(transactionName, ...transactionArgs);
                        const resultStr = Buffer.from(resultBytes).toString('utf8');
                        console.log(JSON.stringify({ id, error: null, result: resultStr ? JSON.parse(resultStr) : null }));
                    } else {
                        // For sprint 7B: real submission with commit wait
                        const commit = await contract.submitAsync(transactionName, { arguments: transactionArgs });
                        const status = await commit.getStatus();
                        const resultBytes = commit.getResult();
                        const transactionId = commit.getTransactionId();
                        
                        const resultStr = Buffer.from(resultBytes).toString('utf8');
                        const parsedResult = resultStr ? JSON.parse(resultStr) : null;
                        
                        console.log(JSON.stringify({ 
                            id, 
                            error: null, 
                            result: {
                                payload: parsedResult,
                                transaction_id: transactionId,
                                block_number: status.blockNumber ? status.blockNumber.toString() : null,
                                successful: status.successful
                            }
                        }));
                    }
                } catch (err) {
                    let errMsg = err.message;
                    if (err.details && err.details.length > 0) {
                        errMsg += ' ' + err.details.map(d => d.message).join(', ');
                    }
                    console.log(JSON.stringify({ id, error: errMsg, result: null }));
                }
            } else {
                console.log(JSON.stringify({ id, error: 'Unknown method', result: null }));
            }
        } catch (e) {
            console.log(JSON.stringify({ id: null, error: 'Internal Error: ' + e.message, result: null }));
        }
    });

    rl.on('close', () => {
        if (gateway) {
            gateway.close();
        }
        if (client) {
            client.close();
        }
        process.exit(0);
    });
}

start();
