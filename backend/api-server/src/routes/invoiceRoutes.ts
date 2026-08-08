import { Router } from 'express';
import { getInvoices, getInvoiceById, createInvoice, updateInvoiceStatus , bulkDeleteInvoices, bulkUpdateInvoiceStatus} from '../controllers/invoiceController';
import { authenticateJWT } from '../middlewares/auth';
import { authorizeRoles } from '../middlewares/rbac';
import { validate } from '../middlewares/validate';
import { createInvoiceBody, listQuery } from '../schemas';

const router = Router();

router.use(authenticateJWT);
router.use(authorizeRoles('Admin', 'Operator'));
router.post('/bulk-delete', bulkDeleteInvoices);
router.post('/bulk-update-status', bulkUpdateInvoiceStatus);


router.get('/', validate({ query: listQuery }), getInvoices);
router.post('/', validate({ body: createInvoiceBody }), createInvoice);
router.get('/:id', getInvoiceById);
router.patch('/:id/status', updateInvoiceStatus);

export default router;
