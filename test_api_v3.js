const https = require('https');

const GEMINI_API_KEY = 'AIzaSyDJlz0midQH41a0_6Vw8iotkN5DC16Vtmc';
const model = 'gemini-1.5-flash-latest'; // Common name for Gemini 1.5 Flash
const endpoint = 'v1beta'; // Let's try v1beta first with -latest suffix

const options = {
  hostname: 'generativelanguage.googleapis.com',
  path: `/${endpoint}/models/${model}:generateContent?key=${GEMINI_API_KEY}`,
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  }
};

const requestBody = JSON.stringify({
  contents: [
    {
      parts: [{ text: "Hello" }],
    },
  ],
});

const req = https.request(options, (res) => {
  let data = '';
  res.on('data', (chunk) => {
    data += chunk;
  });
  res.on('end', () => {
    console.log('Status Code:', res.statusCode);
    console.log('Response:', data);
  });
});

req.on('error', (error) => {
  console.error('Error:', error);
});

req.write(requestBody);
req.end();
