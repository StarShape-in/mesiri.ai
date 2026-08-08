import { Router } from 'express';
import { getUsers, createUser, updateUser, deleteUser } from '../controllers/userController';
import { authenticateJWT } from '../middlewares/auth';
import { authorizeRoles } from '../middlewares/rbac';
import { validate } from '../middlewares/validate';
import { createUserBody, updateUserBody, idParam } from '../schemas';

const router = Router();

// Admin and Operator can view; only Admin can create/edit/deactivate
router.use(authenticateJWT);

router.get('/', authorizeRoles('Admin', 'Operator'), getUsers);
router.post('/', authorizeRoles('Admin'), validate({ body: createUserBody }), createUser);
router.put('/:id', authorizeRoles('Admin'), validate({ params: idParam, body: updateUserBody }), updateUser);
router.delete('/:id', authorizeRoles('Admin'), validate({ params: idParam }), deleteUser);

export default router;
