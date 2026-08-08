import multer from 'multer';

const ALLOWED_MIME_TYPES = new Set([
  'image/jpeg',
  'image/png',
  'image/webp',
  'image/heic',
  'image/heif',
  'application/pdf',
]);

/**
 * Restricts uploads to images + PDF. Without this, any authenticated caller
 * could upload an .html/.svg file, which `express.static('uploads')` would
 * then serve back with a browser-executable content type — a stored XSS
 * vector against whoever opens that document link from the dashboard.
 */
export const imageOrPdfFileFilter: multer.Options['fileFilter'] = (_req, file, cb) => {
  if (ALLOWED_MIME_TYPES.has(file.mimetype)) {
    cb(null, true);
  } else {
    cb(new Error('Only image or PDF files are allowed'));
  }
};
