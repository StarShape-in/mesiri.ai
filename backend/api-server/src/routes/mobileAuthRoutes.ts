import { Router } from 'express';
import { mobileLogin } from '../controllers/mobileAuthController';
import { createAuthRateLimit } from '../middlewares/rateLimit';

const router = Router();

router.post('/login', createAuthRateLimit(), mobileLogin);

export default router;
