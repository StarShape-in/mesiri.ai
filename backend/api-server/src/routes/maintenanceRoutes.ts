import { Router } from 'express';
import { 
  getMaintenanceRecords, 
  getMaintenanceRecordById,
  createMaintenanceRecord, 
  updateMaintenanceRecord, 
  deleteMaintenanceRecord 
} from '../controllers/maintenanceController';
import { authenticateJWT } from '../middlewares/auth';
import { authorizeRoles } from '../middlewares/rbac';

const router = Router();

router.use(authenticateJWT);
router.use(authorizeRoles('Admin', 'Operator'));

router.get('/', getMaintenanceRecords);
router.get('/:id', getMaintenanceRecordById);
router.post('/', createMaintenanceRecord);
router.patch('/:id', updateMaintenanceRecord);
router.delete('/:id', deleteMaintenanceRecord);

export default router;
