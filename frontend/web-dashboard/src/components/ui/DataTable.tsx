import React, { useState, useEffect } from 'react';
import { Search, SlidersHorizontal, Download, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, CheckSquare, X, FileSearch } from 'lucide-react';
import Btn from './Btn';
import { Button } from './button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './table';
import { Input } from './input';
import { Badge } from './badge';
import { cn } from '@/lib/utils';

export interface Column<T> {
  header: string;
  accessor: (row: T, index: number) => React.ReactNode;
  className?: string;
  headerClassName?: string;
}

export interface BulkAction<T> {
  label: string;
  icon?: React.ReactNode;
  variant?: 'primary' | 'secondary' | 'ghost' | 'outline' | 'danger';
  onClick: (selectedRows: T[]) => void | Promise<void>;
}

export interface DataTableProps<T> {
  title?: React.ReactNode;
  subtitle?: string;
  columns: Column<T>[];
  data: T[];
  isLoading?: boolean;
  searchPlaceholder?: string;
  searchValue?: string;
  onSearchChange?: (val: string) => void;
  // Filters & Action Slots
  filterElement?: React.ReactNode;
  actionsElement?: React.ReactNode;
  // Export Action
  onExport?: () => void;
  // Pagination
  currentPage?: number;
  totalPages?: number;
  onPageChange?: (page: number) => void;
  pageSize?: number;
  onPageSizeChange?: (pageSize: number) => void;
  pageSizeOptions?: number[];
  totalRecords?: number;
  // Selection
  enableSelection?: boolean;
  onSelectionChange?: (selectedIndices: number[]) => void;
  // Row Click
  onRowClick?: (row: T) => void;
  // Bulk Actions
  bulkActions?: BulkAction<T>[];
  // State overrides
  isError?: boolean;
  errorTitle?: string;
  errorMessage?: string;
  emptyTitle?: string;
  emptyMessage?: string;
  // Custom height/compactness
  compact?: boolean;
  className?: string;
}

export default function DataTable<T>({
  title,
  subtitle,
  columns,
  data,
  isLoading = false,
  isError = false,
  errorTitle = 'Data Unavailable',
  errorMessage = 'Failed to load records from the server. Please try again.',
  searchPlaceholder = 'Search records...',
  searchValue,
  onSearchChange,
  filterElement,
  actionsElement,
  onExport,
  currentPage,
  totalPages,
  onPageChange,
  pageSize,
  onPageSizeChange,
  pageSizeOptions = [10, 25, 50, 100],
  totalRecords,
  enableSelection = true,
  onSelectionChange,
  onRowClick,
  bulkActions = [],
  emptyTitle = 'No Records Found',
  emptyMessage = 'There are no entries matching your current filters or search query.',
  compact = false,
  className,
}: DataTableProps<T>) {
  // Internal state for client-side pagination when onPageChange is not passed
  const [internalPage, setInternalPage] = useState(1);
  const [internalPageSize, setInternalPageSize] = useState(pageSize || 10);
  const [selectedIndices, setSelectedIndices] = useState<Set<number>>(new Set());

  // Reset internal page if data length changes or search changes
  useEffect(() => {
    if (onPageChange === undefined) {
      setInternalPage(1);
    }
  }, [data.length, searchValue]);

  const isServerPaginated = onPageChange !== undefined;
  const activePage = isServerPaginated ? (currentPage || 1) : internalPage;
  const activePageSize = pageSize !== undefined ? pageSize : internalPageSize;

  const totalCount = totalRecords !== undefined ? totalRecords : data.length;
  const computedTotalPages = totalPages !== undefined 
    ? totalPages 
    : Math.max(1, Math.ceil(totalCount / activePageSize));

  // Display data: server-paginated data is already sliced; client-paginated data is sliced here
  const displayData = isServerPaginated 
    ? data 
    : data.slice((activePage - 1) * activePageSize, activePage * activePageSize);

  const handlePageChange = (newPage: number) => {
    const validPage = Math.max(1, Math.min(newPage, computedTotalPages));
    if (isServerPaginated) {
      onPageChange?.(validPage);
    } else {
      setInternalPage(validPage);
    }
    setSelectedIndices(new Set());
    onSelectionChange?.([]);
  };

  const handlePageSizeChange = (newSize: number) => {
    if (onPageSizeChange) {
      onPageSizeChange(newSize);
    } else {
      setInternalPageSize(newSize);
      setInternalPage(1);
    }
    if (isServerPaginated && onPageChange) {
      onPageChange(1);
    }
    setSelectedIndices(new Set());
    onSelectionChange?.([]);
  };

  const handleSelectAll = () => {
    if (selectedIndices.size === displayData.length && displayData.length > 0) {
      setSelectedIndices(new Set());
      onSelectionChange?.([]);
    } else {
      const newSet = new Set(displayData.map((_, i) => i));
      setSelectedIndices(newSet);
      onSelectionChange?.(Array.from(newSet));
    }
  };

  const clearSelection = () => {
    setSelectedIndices(new Set());
    onSelectionChange?.([]);
  };

  const handleSelectRow = (index: number) => {
    const newSet = new Set(selectedIndices);
    if (newSet.has(index)) {
      newSet.delete(index);
    } else {
      newSet.add(index);
    }
    setSelectedIndices(newSet);
    onSelectionChange?.(Array.from(newSet));
  };

  const fromIndex = totalCount === 0 ? 0 : (activePage - 1) * activePageSize + 1;
  const toIndex = totalCount === 0 ? 0 : Math.min(
    activePage * activePageSize,
    isServerPaginated ? (fromIndex + displayData.length - 1) : totalCount
  );

  const showToolbar = title || onSearchChange !== undefined || filterElement !== undefined || onExport !== undefined || actionsElement !== undefined || enableSelection;

  return (
    <div className={cn("bg-white dark:bg-slate-900 rounded-xl border border-slate-200/80 dark:border-slate-800 shadow-xs overflow-hidden flex flex-col w-full animate-fade-in", className)}>
      
      {/* Table Toolbar Header */}
      {showToolbar && (
        <div className="shrink-0 p-3 sm:p-4 border-b border-slate-200/80 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-900/60 flex flex-wrap items-center justify-between gap-2.5 sm:gap-3">
          {selectedIndices.size > 0 ? (
            <div className="flex items-center flex-wrap gap-2 sm:gap-3 w-full bg-indigo-50/80 dark:bg-indigo-950/40 border border-indigo-200/80 dark:border-indigo-800/80 p-2 rounded-lg transition-all" role="alert">
              <span className="text-xs font-bold text-indigo-700 dark:text-indigo-300 px-2">
                {selectedIndices.size} row{selectedIndices.size > 1 ? 's' : ''} selected
              </span>
              <div className="h-4 w-[1px] bg-indigo-200 dark:bg-indigo-800 hidden sm:block" />
              <div className="flex items-center gap-2 flex-1 flex-wrap">
                {bulkActions.map((action, i) => (
                  <Btn
                    key={i}
                    label={action.label}
                    icon={action.icon}
                    variant={action.variant || 'secondary'}
                    size="sm"
                    onClick={() => {
                      const selectedRows = Array.from(selectedIndices).map(idx => displayData[idx]);
                      action.onClick(selectedRows);
                    }}
                  />
                ))}
              </div>
              <Btn
                label="Clear"
                variant="ghost"
                size="sm"
                onClick={clearSelection}
                className="text-indigo-600 hover:text-indigo-800 hover:bg-indigo-100/60 text-xs font-bold"
              />
            </div>
          ) : (
            <>
              {/* Left Side: Ledger Title & Search / Filter Controls */}
              <div className="flex items-center gap-2.5 sm:gap-3 flex-1 flex-wrap min-w-0">
                {title ? (
                  <div className="flex items-center gap-2.5 mr-2">
                    <h3 className="text-sm font-extrabold text-slate-900 dark:text-slate-100 tracking-tight">
                      {title}
                    </h3>
                    <Badge variant="outline" className="bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700 text-[11px] font-mono font-bold px-2 py-0.5">
                      {totalCount} {totalCount === 1 ? 'record' : 'records'}
                    </Badge>
                    {enableSelection && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleSelectAll}
                        className="h-7 text-xs font-semibold px-2.5 shadow-2xs gap-1.5 border-slate-200/90 dark:border-slate-700/90 hover:bg-slate-100 dark:hover:bg-slate-800"
                      >
                        <CheckSquare className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
                        <span>{selectedIndices.size === displayData.length && displayData.length > 0 ? "Deselect All" : "Select All"}</span>
                      </Button>
                    )}
                  </div>
                ) : (
                  enableSelection && (
                    <div className="flex items-center gap-2.5 mr-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleSelectAll}
                        className="h-7 text-xs font-semibold px-2.5 shadow-2xs gap-1.5 border-slate-200/90 dark:border-slate-700/90 hover:bg-slate-100 dark:hover:bg-slate-800"
                      >
                        <CheckSquare className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
                        <span>{selectedIndices.size === displayData.length && displayData.length > 0 ? "Deselect All" : "Select All"}</span>
                      </Button>
                    </div>
                  )
                )}


                {onSearchChange !== undefined && (
                  <div className="relative w-full sm:w-auto sm:flex-1 sm:max-w-sm sm:min-w-[200px]">
                    <Search size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
                    <Input
                      type="text"
                      placeholder={searchPlaceholder}
                      value={searchValue || ''}
                      onChange={(e) => onSearchChange(e.target.value)}
                      className="w-full pl-9 pr-8 h-9 text-xs bg-white dark:bg-slate-800/80 border-slate-200 dark:border-slate-700 focus-visible:ring-[#E8450F]/20 focus-visible:border-[#E8450F] rounded-lg font-medium"
                      aria-label="Search Table"
                    />
                    {searchValue && (
                      <button 
                        onClick={() => onSearchChange('')}
                        className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 p-0.5"
                        aria-label="Clear search"
                      >
                        <X size={12} />
                      </button>
                    )}
                  </div>
                )}

                {filterElement}
              </div>

              {/* Right Side: Actions & Export */}
              <div className="flex items-center flex-wrap gap-2.5 sm:shrink-0">
                {actionsElement}
                {onExport && (
                  <Btn
                    label="Export"
                    variant="secondary"
                    size="sm"
                    icon={<Download size={13} />}
                    onClick={onExport}
                  />
                )}
              </div>
            </>
          )}
        </div>
      )}

      {/* Main Table Container */}
      <div className="flex-1 overflow-auto min-h-0 w-full">
        <Table className="w-full min-w-[720px]" role="table">
          <TableHeader>
            <TableRow className="bg-slate-50/80 dark:bg-slate-900/80 border-b border-slate-200/80 dark:border-slate-800 hover:bg-slate-50/80">
              {enableSelection && (
                <TableHead className="w-[48px] px-5" />
              )}
              {columns.map((c, i) => (
                <TableHead key={i} className={cn("text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 h-11 px-5", c.headerClassName)}>
                  {c.header}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              // Loading state skeleton rows
              Array.from({ length: activePageSize > 10 ? 10 : activePageSize }).map((_, rowIndex) => (
                <TableRow key={rowIndex} className="border-b border-slate-100 dark:border-slate-800/60">
                  {enableSelection && (
                    <TableCell className="px-5 py-4 w-[48px]">
                      <div className="h-4 skeleton w-4 rounded"></div>
                    </TableCell>
                  )}
                  {columns.map((_, colIndex) => (
                    <TableCell key={colIndex} className="px-5 py-4">
                      <div className="h-4 skeleton w-full max-w-[140px] rounded-md"></div>
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : isError ? (
              // Error State
              <TableRow>
                <TableCell colSpan={enableSelection ? columns.length + 1 : columns.length} className="text-center py-16">
                  <div className="flex flex-col items-center justify-center gap-2 max-w-sm mx-auto">
                    <div className="w-14 h-14 rounded-2xl bg-rose-50 dark:bg-rose-900/20 flex items-center justify-center text-rose-500">
                      <X size={28} className="stroke-[2]" />
                    </div>
                    <p className="text-sm font-bold text-slate-900 dark:text-slate-100 mt-2">{errorTitle}</p>
                    <p className="text-xs text-slate-500 dark:text-slate-400 text-center max-w-xs">{errorMessage}</p>
                  </div>
                </TableCell>
              </TableRow>
            ) : displayData.length === 0 ? (
              // Empty State
              <TableRow>
                <TableCell colSpan={enableSelection ? columns.length + 1 : columns.length} className="text-center py-16">
                  <div className="flex flex-col items-center justify-center gap-2 max-w-sm mx-auto">
                    <div className="w-14 h-14 rounded-2xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-400">
                      <FileSearch size={28} className="stroke-[1.5]" />
                    </div>
                    <p className="text-sm font-bold text-slate-900 dark:text-slate-100 mt-2">{emptyTitle}</p>
                    <p className="text-xs text-slate-500 dark:text-slate-400 text-center max-w-xs">{emptyMessage}</p>
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              // Data Rows
              displayData.map((row, rowIndex) => {
                const isSelected = selectedIndices.has(rowIndex);
                return (
                  <TableRow
                    key={rowIndex}
                    className={cn(
                      "animate-fade-in transition-colors border-b border-slate-100 dark:border-slate-800/60 focus-visible:bg-slate-50 dark:focus-visible:bg-slate-800/80 outline-none",
                      isSelected 
                        ? "bg-indigo-50/25 dark:bg-indigo-950/20 hover:bg-indigo-50/45 dark:hover:bg-indigo-950/30" 
                        : onRowClick 
                          ? "cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/60" 
                          : "hover:bg-slate-50/70 dark:hover:bg-slate-800/40"
                    )}
                    style={{ animationDelay: `${rowIndex * 0.02}s` }}
                    tabIndex={onRowClick ? 0 : undefined}
                    aria-selected={isSelected}
                    role="row"
                    onKeyDown={(e) => {
                      if (onRowClick && (e.key === 'Enter' || e.key === ' ')) {
                        e.preventDefault();
                        onRowClick(row);
                      }
                    }}
                    onClick={(e) => {
                      const target = e.target as HTMLElement;
                      if (
                        target.tagName.toLowerCase() === 'input' ||
                        target.tagName.toLowerCase() === 'button' ||
                        target.closest('button') ||
                        target.closest('a')
                      ) {
                        return;
                      }
                      onRowClick?.(row);
                    }}
                  >
                    {enableSelection && (
                      <TableCell className={cn(compact ? "px-4 py-2.5 w-[44px]" : "px-5 py-4 w-[48px]")}>
                        <input
                          type="checkbox"
                          className="w-4 h-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                          checked={isSelected}
                          onChange={() => handleSelectRow(rowIndex)}
                          aria-label={`Select row ${rowIndex + 1}`}
                        />
                      </TableCell>
                    )}
                    {columns.map((col, colIndex) => (
                      <TableCell key={colIndex} className={cn(compact ? "px-4 py-2.5 text-xs font-medium text-slate-800 dark:text-slate-200" : "px-5 py-4 text-sm font-medium text-slate-800 dark:text-slate-200", col.className)}>
                        {col.accessor(row, rowIndex)}
                      </TableCell>
                    ))}
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </div>

      {/* Spacious Pagination Footer */}
      <div className="shrink-0 p-3 sm:p-4 sm:px-5 border-t border-slate-200/80 dark:border-slate-800 flex flex-wrap items-center justify-between gap-3 bg-slate-50/60 dark:bg-slate-900/60 text-xs font-semibold text-slate-600 dark:text-slate-400">
        {/* Left Side: Rows Per Page & Summary Count */}
        <div className="flex items-center gap-3 sm:gap-4 flex-wrap">
          <div className="flex items-center gap-2">
            <span className="text-slate-500 dark:text-slate-400 font-medium">
              <span className="hidden sm:inline">Rows per page:</span>
              <span className="sm:hidden">Rows:</span>
            </span>
            <select
              value={activePageSize}
              onChange={(e) => handlePageSizeChange(Number(e.target.value))}
              className="h-8 px-2.5 py-1 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-xs font-bold text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 cursor-pointer shadow-2xs"
              aria-label="Rows per page"
            >
              {pageSizeOptions.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          </div>

          <span className="text-slate-500 dark:text-slate-400 font-medium border-l border-slate-200 dark:border-slate-700 pl-4 hidden sm:inline">
            Showing <span className="font-extrabold text-slate-900 dark:text-slate-100">{fromIndex}</span> to <span className="font-extrabold text-slate-900 dark:text-slate-100">{toIndex}</span> of <span className="font-extrabold text-slate-900 dark:text-slate-100">{totalCount}</span> entries
          </span>
        </div>

        {/* Right Side: Page Navigation Buttons */}
        <div className="flex items-center gap-1.5 ml-auto" role="navigation" aria-label="Pagination Navigation">
          <button
            onClick={() => handlePageChange(1)}
            disabled={activePage === 1 || isLoading}
            aria-label="First page"
            className="p-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-2xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#E8450F]/40"
          >
            <ChevronsLeft size={14} />
          </button>

          <button
            onClick={() => handlePageChange(activePage - 1)}
            disabled={activePage === 1 || isLoading}
            aria-label="Previous page"
            className="p-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-2xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#E8450F]/40"
          >
            <ChevronLeft size={14} />
          </button>

          <div className="flex items-center gap-1 px-2" aria-live="polite">
            <span className="px-2.5 py-1 text-xs font-extrabold text-slate-900 dark:text-slate-100 bg-white dark:bg-slate-800 rounded-md border border-slate-200 dark:border-slate-700 shadow-2xs">
              {activePage}
            </span>
            <span className="text-slate-400 text-xs font-medium">/</span>
            <span className="text-slate-600 dark:text-slate-400 text-xs font-bold">{computedTotalPages}</span>
          </div>

          <button
            onClick={() => handlePageChange(activePage + 1)}
            disabled={activePage >= computedTotalPages || isLoading}
            aria-label="Next page"
            className="p-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-2xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#E8450F]/40"
          >
            <ChevronRight size={14} />
          </button>

          <button
            onClick={() => handlePageChange(computedTotalPages)}
            disabled={activePage >= computedTotalPages || isLoading}
            aria-label="Last page"
            className="p-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-2xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#E8450F]/40"
          >
            <ChevronsRight size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}


