import { useState, useRef } from 'react';
import { UploadCloud, FileText, Loader2, AlertCircle } from 'lucide-react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { documentService, DocType } from '@/services/documentService';
import Btn from './Btn';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './dialog';

interface UploadDocumentModalProps {
  isOpen: boolean;
  onClose: () => void;
  entityType: string;
  entityId: string;
  docType?: DocType;
  onUploadSuccess?: () => void;
}

export default function UploadDocumentModal({
  isOpen,
  onClose,
  entityType,
  entityId,
  docType,
  onUploadSuccess,
}: UploadDocumentModalProps) {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedDocType, setSelectedDocType] = useState<DocType>(docType || 'POD');
  const [issueDate, setIssueDate] = useState('');
  const [expiryDate, setExpiryDate] = useState('');
  const [isConfidential, setIsConfidential] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const uploadMutation = useMutation({
    mutationFn: (formData: FormData) => documentService.upload(formData),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] });
      if (onUploadSuccess) onUploadSuccess();
      handleClose();
    },
    onError: (err: any) => {
      setError(err.response?.data?.error?.message || err.message || 'Failed to upload document');
    }
  });

  const handleClose = () => {
    setSelectedFile(null);
    setIssueDate('');
    setExpiryDate('');
    setIsConfidential(false);
    setError(null);
    onClose();
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setSelectedFile(e.target.files[0]);
      setError(null);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setError('Please select a file to upload.');
      return;
    }

    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('entity_type', entityType);
    formData.append('entity_id', entityId);
    formData.append('doc_type', selectedDocType);
    if (issueDate) formData.append('issue_date', new Date(issueDate).toISOString());
    if (expiryDate) formData.append('expiry_date', new Date(expiryDate).toISOString());
    formData.append('is_confidential', isConfidential.toString());

    uploadMutation.mutate(formData);
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => {
      if (!open && !uploadMutation.isPending) handleClose();
    }}>
      <DialogContent className="w-full max-w-md rounded-lg p-0 border-gray-100 shadow-xl overflow-hidden max-h-[90vh] flex flex-col">
        
        {/* Header */}
        <DialogHeader className="px-6 py-4 border-b border-gray-100 m-0">
          <DialogTitle className="text-lg font-bold text-gray-900">Upload Document</DialogTitle>
        </DialogHeader>

        {/* Content */}
        <div className="p-6 overflow-y-auto">
          <form onSubmit={handleSubmit} className="space-y-5">
            
            {/* File Dropzone */}
            <div>
              <div 
                onClick={() => fileInputRef.current?.click()}
                className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-all
                  ${selectedFile ? 'border-green-500 bg-green-50' : 'border-gray-300 hover:border-[#E8450F] hover:bg-orange-50/50'}`}
              >
                <input 
                  type="file" 
                  ref={fileInputRef} 
                  onChange={handleFileSelect} 
                  className="hidden" 
                  accept=".pdf,.png,.jpg,.jpeg"
                />
                
                {selectedFile ? (
                  <div className="flex flex-col items-center">
                    <div className="w-12 h-12 bg-green-100 text-green-600 rounded-full flex items-center justify-center mb-3">
                      <FileText size={24} />
                    </div>
                    <p className="text-sm font-semibold text-gray-900 truncate max-w-[250px]">{selectedFile.name}</p>
                    <p className="text-xs text-gray-500 mt-1">{(selectedFile.size / 1024 / 1024).toFixed(2)} MB</p>
                  </div>
                ) : (
                  <div className="flex flex-col items-center">
                    <div className="w-12 h-12 bg-gray-100 text-gray-400 rounded-full flex items-center justify-center mb-3">
                      <UploadCloud size={24} />
                    </div>
                    <p className="text-sm font-semibold text-gray-900">Click to upload file</p>
                    <p className="text-xs text-gray-500 mt-1">PDF, PNG, JPG (Max 50MB)</p>
                  </div>
                )}
              </div>
            </div>

            {/* Document Details */}
            <div className="space-y-4 pt-2">
              <div>
                <label className="block text-xs font-bold text-gray-900 mb-1.5">Document Type</label>
                <select 
                  value={selectedDocType}
                  onChange={(e) => setSelectedDocType(e.target.value as DocType)}
                  className="w-full bg-gray-50 border border-gray-200 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-[#E8450F]"
                  disabled={!!docType} // If docType passed as prop, disable changing it
                >
                  <option value="POD">Proof of Delivery (POD)</option>
                  <option value="Contract">Contract</option>
                  <option value="DriverLicense">Driver License</option>
                  <option value="VehicleRegistration">Vehicle Registration</option>
                  <option value="Insurance">Insurance</option>
                  <option value="Waybill">Waybill</option>
                  <option value="Invoice">Invoice</option>
                  <option value="CustomsClearance">Customs Clearance</option>
                </select>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-gray-900 mb-1.5">Issue Date (Optional)</label>
                  <input 
                    type="date" 
                    value={issueDate}
                    onChange={(e) => setIssueDate(e.target.value)}
                    className="w-full bg-gray-50 border border-gray-200 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-[#E8450F]"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-gray-900 mb-1.5">Expiry Date (Optional)</label>
                  <input 
                    type="date" 
                    value={expiryDate}
                    onChange={(e) => setExpiryDate(e.target.value)}
                    className="w-full bg-gray-50 border border-gray-200 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-[#E8450F]"
                  />
                </div>
              </div>

              <label className="flex items-center gap-2 cursor-pointer pt-1">
                <input 
                  type="checkbox" 
                  checked={isConfidential}
                  onChange={(e) => setIsConfidential(e.target.checked)}
                  className="w-4 h-4 text-[#E8450F] rounded border-gray-300 focus:ring-[#E8450F]"
                />
                <span className="text-sm text-gray-700 font-medium">Mark as confidential</span>
              </label>
            </div>

            {error && (
              <div className="flex items-start gap-2 p-3 bg-red-50 text-red-600 rounded-lg text-sm">
                <AlertCircle size={16} className="mt-0.5 shrink-0" />
                <p>{error}</p>
              </div>
            )}
          </form>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-100 bg-gray-50/50">
          <Btn 
            label="Cancel" 
            variant="outline" 
            onClick={handleClose} 
            disabled={uploadMutation.isPending} 
          />
          <Btn 
            label="Upload Document" 
            onClick={handleSubmit} 
            disabled={!selectedFile || uploadMutation.isPending}
            icon={uploadMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <UploadCloud size={16} />}
          />
        </div>

      </DialogContent>
    </Dialog>
  );
}
