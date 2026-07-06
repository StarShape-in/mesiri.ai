export type AppScope =
  | {
      mode: 'portfolio';
    }
  | {
      mode: 'project';
      projectId: string;
      projectName: string;
    }
  | {
      mode: 'site';
      projectId: string;
      projectName: string;
      siteId: string;
      siteName: string;
    };

export type ProjectItem = {
  id: string;
  name: string;
};

export type SiteItem = {
  id: string;
  name: string;
  projectId: string;
};
