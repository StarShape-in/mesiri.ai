import { Router } from 'express';
import { getNotifications, markAsRead, sendBulkCommunication } from '../controllers/notificationController';
import { authenticateJWT } from '../middlewares/auth';
import { authorizeRoles } from '../middlewares/rbac';

const router = Router();

router.use(authenticateJWT);
router.use(authorizeRoles('Admin', 'Operator'));

router.get('/', getNotifications);
router.patch('/:id/read', markAsRead);
router.post('/bulk-send', sendBulkCommunication);

export default router;
