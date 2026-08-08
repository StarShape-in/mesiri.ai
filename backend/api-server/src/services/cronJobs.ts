import cron from 'node-cron';
import { logger } from '../utils/logger';
import { prisma, io } from '../index';
import { iccesService } from './iccesService';

export const initCronJobs = () => {
  logger.info('🔄 Initializing ICCES Cron Jobs...');

  // 1. Telemetry Sync (Runs every 30 seconds)
  // Pulls ICCES GPS data and broadcasts to WebSockets as a fallback
  cron.schedule('*/30 * * * * *', async () => {
    try {
      // Find all In Transit trips that have a vehicle with an ICCES tracker
      const activeTrips = await prisma.trip.findMany({
        where: { status: 'InTransit' },
        include: { vehicle: true }
      });

      const today = new Date().toISOString().split('T')[0];

      for (const trip of activeTrips) {
        if (trip.vehicle && trip.vehicle.icces_device_id) {
          const deviceId = trip.vehicle.icces_device_id;
          
          // Fetch ICCES data
          const trackingData = await iccesService.getLiveTrackingData(deviceId, today);
          
          if (trackingData && trackingData.length > 0) {
            // Find the most recent event
            const eventList = trackingData[0].eventList;
            if (eventList && eventList.length > 0) {
              // ICCES returns an array, latest is usually first or last. Assume last for now.
              const latestEvent = eventList[eventList.length - 1];
              
              if (latestEvent.latitude && latestEvent.longitude) {
                const gpsData = {
                  lat: parseFloat(latestEvent.latitude),
                  lng: parseFloat(latestEvent.longitude),
                  speed: parseFloat(latestEvent.speedKPH || '0'),
                  heading: parseFloat(latestEvent.heading || '0'),
                  source: 'ICCES_FALLBACK'
                };

                // Update vehicle last known location in DB
                await prisma.vehicle.update({
                  where: { id: trip.vehicle.id },
                  data: { 
                    last_lat: gpsData.lat, 
                    last_lng: gpsData.lng
                  }
                });

                // Broadcast to whoever has joined this trip's room (dashboards/driver)
                io.to(`trip:${trip.id}`).emit(`trip:location_update:${trip.id}`, gpsData);
                // logger.info(`[ICCES] Broadcasted location for Trip ${trip.ref_id}`);
              }
            }
          }
        }
      }
    } catch (error) {
      logger.error({ err: error }, '[CRON] Error in Telemetry Sync:');
    }
  });

  // 2. Daily Vehicle Status Sync (Runs at 2 AM every day)
  cron.schedule('0 2 * * *', async () => {
    logger.info('🔄 Running Daily ICCES Vehicle Sync...');
    try {
      const vehicles = await iccesService.getVehicles();
      if (Array.isArray(vehicles)) {
        for (const v of vehicles) {
          if (v.deviceID) {
            // If we have a matching truck in our fleet, sync its odometer
            await prisma.vehicle.updateMany({
              where: { icces_device_id: v.deviceID },
              data: {
                current_odometer: parseFloat(v.lastOdometerKM || '0')
              }
            });
          }
        }
        logger.info(`✅ Synced ${vehicles.length} vehicles from ICCES.`);
      }
    } catch (error) {
      logger.error({ err: error }, '[CRON] Error in Daily Vehicle Sync:');
    }
  });
  
  // 3. Alerts Sync (Runs every 1 minute)
  cron.schedule('* * * * *', async () => {
    // logger.info('🔄 Running ICCES Alerts Sync...');
    try {
      const alertsResponse = await iccesService.getAlerts();
      // Depending on actual API payload, typically it's an array or wrapped in data
      const alerts = Array.isArray(alertsResponse) ? alertsResponse : (alertsResponse?.data || []);
      
      if (alerts && alerts.length > 0) {
        // Fetch users who should receive notifications
        const operatorsAndAdmins = await prisma.user.findMany({
          where: { role: { in: ['Admin', 'Operator'] }, isActive: true }
        });

        const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000);

        for (const alert of alerts) {
          if (alert.deviceID) {
            const vehicle = await prisma.vehicle.findUnique({
              where: { icces_device_id: alert.deviceID }
            });

            if (vehicle) {
              const message = `ICCES Alert on ${vehicle.plate_number}: ${alert.alertType || 'Critical Tracking Issue'}`;
              
              // Skip if we already logged this exact alert for this vehicle recently
              const recentAlert = await prisma.notification.findFirst({
                where: {
                  entity_id: vehicle.id,
                  entity_type: 'Vehicle',
                  message: message,
                  created_at: { gte: fiveMinutesAgo }
                }
              });

              if (recentAlert) {
                continue;
              }
              
              for (const user of operatorsAndAdmins) {
                const newNotification = await prisma.notification.create({
                  data: {
                    userId: user.id,
                    title: 'Hardware Alert',
                    message,
                    type: 'Emergency',
                    entity_type: 'Vehicle',
                    entity_id: vehicle.id
                  }
                });
                
                // Broadcast for real-time toaster — to this user's room only
                io.to(`user:${user.id}`).emit('system:notification', newNotification);
              }
            }
          }
        }
      }
    } catch (error) {
      logger.error({ err: error }, '[CRON] Error in Alerts Sync:');
    }
  });
};
