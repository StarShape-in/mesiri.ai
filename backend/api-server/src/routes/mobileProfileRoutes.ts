import { Router } from 'express';
import { getProfile } from '../controllers/mobileProfileController';
import { authenticateJWT } from '../middlewares/auth';
import { authorizeRoles } from '../middlewares/rbac';

const router = Router();

router.use(authenticateJWT);
router.use(authorizeRoles('Driver'));

router.get('/', getProfile);

export default router;
