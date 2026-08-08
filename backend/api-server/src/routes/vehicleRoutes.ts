import { Router } from 'express';
import { getVehicles, getVehicleById, createVehicle, updateVehicle, deleteVehicle , bulkDeleteVehicles, bulkUpdateVehicleStatus, getVehicleFinancials } from '../controllers/vehicleController';
import { authenticateJWT } from '../middlewares/auth';
import { authorizeRoles } from '../middlewares/rbac';
import { validate } from '../middlewares/validate';
import { createVehicleBody, updateVehicleBody, listQuery, idParam } from '../schemas';

const router = Router();

router.use(authenticateJWT);
router.use(authorizeRoles('Admin', 'Operator'));
router.post('/bulk-delete', bulkDeleteVehicles);
router.post('/bulk-update-status', bulkUpdateVehicleStatus);


router.get('/', validate({ query: listQuery }), getVehicles);
router.post('/', validate({ body: createVehicleBody }), createVehicle);
router.get('/:id/financials', validate({ params: idParam }), getVehicleFinancials);
router.get('/:id', validate({ params: idParam }), getVehicleById);
router.patch('/:id', validate({ params: idParam, body: updateVehicleBody }), updateVehicle);
router.delete('/:id', validate({ params: idParam }), deleteVehicle);

export default router;
