import { Router } from 'express';
import { getSummary, getFleetPerformance, getDriverPerformance, getRevenueReport, getCustomReport } from '../controllers/reportsController';
import { getDelayLog, getDelayGrid, getDelayAnalysis } from '../controllers/delayReportsController';
import { authenticateJWT } from '../middlewares/auth';
import { authorizeRoles } from '../middlewares/rbac';

const router = Router();

router.use(authenticateJWT);
router.use(authorizeRoles('Admin', 'Operator'));

// Dashboard summary KPIs + trip distribution + monthly revenue chart
router.get('/summary', getSummary);

// Fleet utilization per vehicle
router.get('/fleet', getFleetPerformance);

// Driver performance metrics
router.get('/drivers', getDriverPerformance);

// Revenue breakdown by month
router.get('/revenue', getRevenueReport);

// Instant Custom Reports
router.get('/custom', getCustomReport);

// Delay reporting. All three take the same filters (date range, customer,
// driver, vehicle, reason) so one filter bar on the page drives every view.
router.get('/delays', getDelayLog);
router.get('/delays/grid', getDelayGrid);
router.get('/delays/analysis', getDelayAnalysis);

export default router;
