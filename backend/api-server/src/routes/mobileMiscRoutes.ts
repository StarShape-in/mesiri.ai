import { Router } from 'express';
import { getDriverDocuments } from '../controllers/mobileDocumentController';
import { getAssignedVehicle } from '../controllers/mobileVehicleController';
import { authenticateJWT } from '../middlewares/auth';
import { authorizeRoles } from '../middlewares/rbac';

const router = Router();

router.use(authenticateJWT);
router.use(authorizeRoles('Driver'));

router.get('/documents', getDriverDocuments);
router.get('/vehicle', getAssignedVehicle);

export default router;
