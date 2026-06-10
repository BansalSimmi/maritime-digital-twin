import React from 'react';
import { Outlet } from 'react-router-dom';
import Topbar from './Topbar';
import Sidebar from './Sidebar';

const Layout = () => {
  return (
    <div id="app" className="on">
      <Topbar />
      <div className="mlayout">
        <Sidebar />
        <div className="content">
          <Outlet />
        </div>
      </div>
    </div>
  );
};

export default Layout;
