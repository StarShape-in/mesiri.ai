import { Router } from 'express';
import {
  getTrips, getTripById, createTrip, updateTripStatus, approveDriverPayment,
  dispatchTrip, replaceDriver, pickupArrive, pickupVerify, deliveryVerify,
  bulkDeleteTrips, bulkUpdateTripStatus, getUnsettledCompletedTrips, updateTripFinancials,
  logStopDelay
} from '../controllers/tripController';
import { authenticateJWT } from '../middlewares/auth';
import { authorizeRoles } from '../middlewares/rbac';
import { validate } from '../middlewares/validate';
import { createTripBody, listQuery, logStopDelayBody } from '../schemas';

const router = Router();

router.use(authenticateJWT);
router.use(authorizeRoles('Admin', 'Operator'));
router.get('/unsettled', getUnsettledCompletedTrips);
router.post('/bulk-delete', bulkDeleteTrips);
router.post('/bulk-update-status', bulkUpdateTripStatus);


router.get('/', validate({ query: listQuery }), getTrips);
router.post('/', validate({ body: createTripBody }), createTrip);
router.get('/:id', getTripById);
router.patch('/:id/status', updateTripStatus);
router.patch('/:id/financials', updateTripFinancials);
router.post('/:id/payment/approve', approveDriverPayment);

// Phase 1: Dispatch & Assignment
router.post('/:id/dispatch', dispatchTrip);
router.post('/:id/replace-driver', replaceDriver);

// Why a stop ran late — operator-filled, drivers never see this.
router.patch('/:id/stops/:stopId/delay', validate({ body: logStopDelayBody }), logStopDelay);

// Phase 2: Driver Workflow
router.post('/:id/pickup/arrive', pickupArrive);
router.post('/:id/pickup/verify', pickupVerify);
router.post('/:id/delivery/verify', deliveryVerify);

export default router;

