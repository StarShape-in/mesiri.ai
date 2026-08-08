import { Router } from 'express';
import { getCurrentTrip, getTripHistory, updateTripStatus, uploadTripPhoto } from '../controllers/mobileTripController';
import { authenticateJWT } from '../middlewares/auth';
import { authorizeRoles } from '../middlewares/rbac';
import { upload } from '../middlewares/upload';

const router = Router();

router.use(authenticateJWT);
router.use(authorizeRoles('Driver'));

router.get('/current', getCurrentTrip);
router.get('/history', getTripHistory);
router.post('/:id/status', updateTripStatus);
router.post('/:id/photo', upload.single('file'), uploadTripPhoto);

export default router;
