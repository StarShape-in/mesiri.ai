import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from './card';

interface FormSectionProps {
  title: string;
  description?: string;
  children: React.ReactNode;
}

export default function FormSection({ title, description, children }: FormSectionProps) {
  return (
    <Card className="mb-6 shadow-sm">
      <CardHeader className="border-b border-border pb-4">
        <CardTitle className="text-sm font-bold text-foreground">{title}</CardTitle>
        {description && (
          <CardDescription className="text-xs font-medium">{description}</CardDescription>
        )}
      </CardHeader>
      <CardContent className="grid grid-cols-1 gap-5 pt-4 md:grid-cols-2">
        {children}
      </CardContent>
    </Card>
  );
}
