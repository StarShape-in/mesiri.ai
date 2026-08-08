import { Router } from 'express';
import { raiseEmergency } from '../controllers/mobileEmergencyController';
import { authenticateJWT } from '../middlewares/auth';
import { authorizeRoles } from '../middlewares/rbac';
import { upload } from '../middlewares/upload';

const router = Router();

router.use(authenticateJWT);
router.use(authorizeRoles('Driver'));

router.post('/', upload.array('photos', 4), raiseEmergency);

export default router;
