import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, UploadCloud, FileText, Calendar, Trash2, CheckCircle, AlertTriangle, Eye } from 'lucide-react';

import DashboardLayout from '@/components/layout/DashboardLayout';
import Btn from '@/components/ui/Btn';
import { documentService, DocType, MerconDocument } from '@/services/documentService';
import { driverService } from '@/services/driverService';

export default function DriverDocumentsPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // New Doc Form
  const [file, setFile] = useState<File | null>(null);
  const [docType, setDocType] = useState<DocType>('DriverLicense');
  const [issueDate, setIssueDate] = useState('');
  const [expiryDate, setExpiryDate] = useState('');

  // Fetch driver
  const { data: driver } = useQuery({
    queryKey: ['driver', id],
    queryFn: () => driverService.getById(id!),
    enabled: !!id,
  });

  // Fetch documents
  const { data: docsRes, isLoading: isLoadingDocs } = useQuery({
    queryKey: ['documents', 'Driver', id],
    queryFn: () => documentService.getAll({ entity_type: 'Driver', entity_id: id, per_page: 50 }),
    enabled: !!id,
  });

  const documents = docsRes?.data || [];

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || !id) return;

    setIsUploading(true);
    setError(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('entity_type', 'Driver');
    formData.append('entity_id', id);
    formData.append('doc_type', docType);
    if (issueDate) formData.append('issue_date', new Date(issueDate).toISOString());
    if (expiryDate) formData.append('expiry_date', new Date(expiryDate).toISOString());

    try {
      await documentService.upload(formData);
      // Reset form
      setFile(null);
      setDocType('DriverLicense');
      setIssueDate('');
      setExpiryDate('');
      // Invalidate query
      queryClient.invalidateQueries({ queryKey: ['documents', 'Driver', id] });
    } catch (err: any) {
      setError(err.response?.data?.error?.message || err.message || 'Upload failed');
    } finally {
      setIsUploading(false);
    }
  };

  const deleteMutation = useMutation({
    mutationFn: (docId: string) => documentService.delete(docId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents', 'Driver', id] });
    },
  });

  const getStatusBadge = (doc: MerconDocument) => {
    switch (doc.status) {
      case 'Verified':
        return <span className="bg-green-100 text-green-700 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider">Verified</span>;
      case 'Rejected':
        return <span className="bg-red-100 text-red-700 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider">Rejected</span>;
      case 'Expired':
        return <span className="bg-orange-100 text-orange-700 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider">Expired</span>;
      default:
        return <span className="bg-blue-100 text-blue-700 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider">Pending</span>;
    }
  };

  return (
    <DashboardLayout 
      active="Drivers" 
      title={`Driver Documents: ${driver?.first_name || ''} ${driver?.last_name || ''}`}
    >
      <div className="px-4 sm:px-6 pb-6 max-w-5xl">
        <button 
          onClick={() => navigate(`/drivers/${id}`)}
          className="flex items-center gap-2 text-sm font-semibold text-[#6E6E80] hover:text-[#111] transition-colors mb-6"
        >
          <ArrowLeft size={16} /> Back to Driver Details
        </button>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Upload Form */}
          <div className="lg:col-span-1">
            <div className="bg-white border border-black/[0.08] rounded-lg p-5 shadow-sm sticky top-24">
              <h3 className="text-sm font-bold text-[#111] mb-4 flex items-center gap-2">
                <UploadCloud size={16} className="text-[#E8450F]" /> Upload Document
              </h3>
              
              <form onSubmit={handleUpload} className="space-y-4">
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-bold text-[#111]">Document Type</label>
                  <select
                    value={docType}
                    onChange={(e) => setDocType(e.target.value as DocType)}
                    className="w-full bg-[#F5F5F7] border border-transparent rounded-lg px-4 py-2.5 text-sm font-medium text-[#111] outline-none"
                  >
                    <option value="DriverLicense">Driver License</option>
                    <option value="Insurance">Medical/Insurance</option>
                    <option value="Contract">Contract</option>
                    <option value="CustomsClearance">ID / Iqama</option>
                  </select>
                </div>

                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-bold text-[#111]">Issue Date (Optional)</label>
                  <input
                    type="date"
                    value={issueDate}
                    onChange={(e) => setIssueDate(e.target.value)}
                    className="w-full bg-[#F5F5F7] border border-transparent rounded-lg px-4 py-2.5 text-sm font-medium text-[#111] outline-none"
                  />
                </div>

                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-bold text-[#111]">Expiry Date (Optional)</label>
                  <input
                    type="date"
                    value={expiryDate}
                    onChange={(e) => setExpiryDate(e.target.value)}
                    className="w-full bg-[#F5F5F7] border border-transparent rounded-lg px-4 py-2.5 text-sm font-medium text-[#111] outline-none"
                  />
                </div>

                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-bold text-[#111]">File</label>
                  <input
                    type="file"
                    onChange={(e) => setFile(e.target.files?.[0] || null)}
                    className="w-full text-sm font-medium file:mr-4 file:py-2 file:px-4 file:rounded-none file:border-0 file:text-xs file:font-bold file:bg-[#E8450F]/10 file:text-[#E8450F] hover:file:bg-[#E8450F]/20 cursor-pointer text-[#6E6E80]"
                    required
                  />
                </div>

                {error && (
                  <p className="text-xs font-semibold text-red-500 bg-red-50 p-2 rounded-lg">{error}</p>
                )}

                <Btn 
                  label={isUploading ? 'Uploading...' : 'Upload Document'} 
                  type="submit" 
                  disabled={!file || isUploading} 
                  className="w-full justify-center"
                />
              </form>
            </div>
          </div>

          {/* Document List */}
          <div className="lg:col-span-2">
            <div className="bg-white border border-black/[0.08] rounded-lg shadow-sm overflow-hidden min-h-[400px]">
              <div className="p-5 border-b border-black/[0.04]">
                <h3 className="text-sm font-bold text-[#111] flex items-center gap-2">
                  <FileText size={16} className="text-[#E8450F]" /> Uploaded Documents
                </h3>
              </div>
              
              {isLoadingDocs ? (
                <div className="p-8 text-center text-[#6E6E80] text-sm font-medium">Loading documents...</div>
              ) : documents.length === 0 ? (
                <div className="p-12 text-center text-[#6E6E80] flex flex-col items-center">
                  <FileText size={48} className="mb-4 opacity-20" />
                  <p className="text-sm font-medium">No documents uploaded yet.</p>
                  <p className="text-xs mt-1">Use the form to upload licenses, IDs, or contracts.</p>
                </div>
              ) : (
                <div className="p-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                  {documents.map((doc) => {
                    const fileUrl = doc.file_url.startsWith('http') ? doc.file_url : `${import.meta.env.VITE_API_URL}${doc.file_url}`;
                    const isExpired = doc.expiry_date && new Date(doc.expiry_date) < new Date();
                    
                    return (
                      <div key={doc.id} className="border border-black/[0.06] rounded-lg p-4 hover:shadow-sm transition-shadow relative bg-[#F9F9FB]">
                        <div className="flex justify-between items-start mb-3">
                          <div className="flex items-center gap-2">
                            <div className="w-8 h-8 rounded-lg bg-white border border-black/[0.06] flex items-center justify-center">
                              <FileText size={14} className="text-[#E8450F]" />
                            </div>
                            <div>
                              <p className="text-sm font-bold text-[#111]">{doc.doc_type}</p>
                              {getStatusBadge(doc)}
                            </div>
                          </div>
                          <button 
                            onClick={() => deleteMutation.mutate(doc.id)}
                            className="text-[#6E6E80] hover:text-red-500 transition-colors p-1"
                            title="Delete"
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                        
                        <div className="space-y-1 mb-4">
                          {doc.expiry_date && (
                            <p className={`text-xs font-medium flex items-center gap-1.5 ${isExpired ? 'text-red-600 font-bold' : 'text-[#6E6E80]'}`}>
                              <Calendar size={12} /> Expiry: {new Date(doc.expiry_date).toLocaleDateString()}
                              {isExpired && <AlertTriangle size={12} />}
                            </p>
                          )}
                          <p className="text-[10px] text-[#9898A4] font-medium">
                            Uploaded: {new Date(doc.createdAt).toLocaleDateString()}
                          </p>
                        </div>

                        <a 
                          href={fileUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center justify-center gap-1.5 w-full py-2 bg-white border border-black/[0.08] rounded-lg text-xs font-bold text-[#111] hover:bg-black/[0.02] transition-colors"
                        >
                          <Eye size={14} /> View Document
                        </a>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
