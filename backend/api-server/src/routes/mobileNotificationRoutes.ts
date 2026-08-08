import { Router } from 'express';
import { getMobileNotifications, markMobileNotificationRead } from '../controllers/mobileNotificationController';
import { authenticateJWT } from '../middlewares/auth';
import { authorizeRoles } from '../middlewares/rbac';

const router = Router();

router.use(authenticateJWT);
router.use(authorizeRoles('Driver'));

router.get('/', getMobileNotifications);
router.post('/:id/read', markMobileNotificationRead);

export default router;
