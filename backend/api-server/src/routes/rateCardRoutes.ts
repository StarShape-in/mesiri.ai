import { Router } from 'express';
import { 
  createRateCard, 
  getRateCards, 
  getRateCardById, 
  updateRateCard, 
  deleteRateCard 
, bulkDeleteRateCards} from '../controllers/rateCardController';
import { authenticateJWT } from '../middlewares/auth';
import { authorizeRoles } from '../middlewares/rbac';

const router = Router();

// All RateCard routes are protected
router.use(authenticateJWT);
router.use(authorizeRoles('Admin', 'Operator'));
router.post('/bulk-delete', bulkDeleteRateCards);


router.post('/', createRateCard);
router.get('/', getRateCards);
router.get('/:id', getRateCardById);
router.put('/:id', updateRateCard);
router.delete('/:id', deleteRateCard);

export default router;
