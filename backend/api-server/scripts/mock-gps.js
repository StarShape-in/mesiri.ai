const { io } = require('socket.io-client');

const socket = io('http://localhost:3000');
const tripId = process.argv[2];

if (!tripId) {
  console.log('Please provide a tripId argument');
  process.exit(1);
}

let lat = 24.7136;
let lng = 46.6753;
let speed = 65;

socket.on('connect', () => {
  console.log('Driver connected to Socket.io');
  
  let count = 0;
  const interval = setInterval(() => {
    count++;
    if (count > 15) {
      console.log('Finished simulating GPS trip');
      process.exit(0);
    }

    lat += 0.0001;
    lng += 0.0001;
    speed = Math.floor(Math.random() * 20) + 70; // 70-90 km/h

    const data = {
      tripId,
      driverId: 'mock-driver-123',
      lat,
      lng,
      speed
    };

    console.log('Sending GPS update:', data);
    socket.emit('driver:location_update', data);
  }, 2000); // send every 2 seconds for testing
});
