import { Router } from 'express';
import { getDrivers, getDriverById, createDriver, updateDriver, deleteDriver , bulkDeleteDrivers, bulkUpdateDriverStatus} from '../controllers/driverController';
import { authenticateJWT } from '../middlewares/auth';
import { authorizeRoles } from '../middlewares/rbac';
import { validate } from '../middlewares/validate';
import { createDriverBody, updateDriverBody, listQuery } from '../schemas';

const router = Router();

// Protect all driver routes
router.use(authenticateJWT);
router.use(authorizeRoles('Admin', 'Operator'));
router.post('/bulk-delete', bulkDeleteDrivers);
router.post('/bulk-update-status', bulkUpdateDriverStatus);


router.get('/', validate({ query: listQuery }), getDrivers);
router.post('/', validate({ body: createDriverBody }), createDriver);
router.get('/:id', getDriverById);
router.patch('/:id', validate({ body: updateDriverBody }), updateDriver);
router.delete('/:id', deleteDriver);

export default router;
