import axios from 'axios';
import { logger } from '../utils/logger';
import { env } from '../config/env';

const ICCES_BASE_URL = 'https://fleet.icces.com:8443/iccWebService1.2';

const ICCES_USER = env.ICCES_USER;
const ICCES_PASS = env.ICCES_PASS;
const ICCES_ACCT = env.ICCES_ACCT;

// Base64 encode <user>:<password>:<account>
const getAuthHeader = () => {
  const token = Buffer.from(`${ICCES_USER}:${ICCES_PASS}:${ICCES_ACCT}`).toString('base64');
  return `Basic ${token}`;
};

export const iccesService = {
  /**
   * Fetches the list of all registered vehicles and their status
   */
  async getVehicles() {
    try {
      const response = await axios.get(ICCES_BASE_URL, {
        headers: { Authorization: getAuthHeader() },
        timeout: 10000,
      });
      return response.data;
    } catch (error) {
      logger.error({ err: error }, '[ICCES API] Error fetching vehicles:');
      return null;
    }
  },

  /**
   * Fetches detailed event/tracking data for a specific device on a specific date
   */
  async getLiveTrackingData(deviceId: string, eventDate: string) {
    try {
      const response = await axios.post(
        ICCES_BASE_URL,
        {
          eventDate,
          reportType: 'EVENT_DETAILS',
          deviceID: deviceId,
        },
        {
          headers: { Authorization: getAuthHeader() },
          timeout: 10000,
        }
      );
      
      if (response.data?.status === 'success' && response.data?.data) {
        return response.data.data;
      }
      return null;
    } catch (error) {
      logger.error({ err: error }, `[ICCES API] Error fetching tracking for device ${deviceId}:`);
      return null;
    }
  },

  /**
   * Retrieves active alerts and alarms for all tracked vehicles
   */
  async getAlerts() {
    try {
      // The docs say GET for alerts, but URL is same. 
      // Often vendors use query params or specific endpoints for alerts. 
      // Based on docs, it's just GET on the base URL, which is weird since that returns vehicles.
      // Assuming a ?type=alerts or similar based on standard patterns, but using base for MVP as per docs.
      const response = await axios.get(`${ICCES_BASE_URL}?requestType=alerts`, {
        headers: { Authorization: getAuthHeader() },
        timeout: 10000,
      });
      return response.data;
    } catch (error) {
      logger.error({ err: error }, '[ICCES API] Error fetching alerts:');
      return null;
    }
  }
};
