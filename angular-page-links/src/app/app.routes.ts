import { Routes } from '@angular/router';
import { Home } from './pages/home/home';
import { Orders } from './pages/orders/orders';
import { Reports } from './pages/reports/reports';
import { Admin } from './pages/admin/admin';

// Each route maps a URL to a component ("page").
// To link a button to a page, the button's routerLink must match one of these paths.
export const routes: Routes = [
  { path: '', component: Home, title: 'Home' },
  { path: 'orders', component: Orders, title: 'Orders' },
  { path: 'reports', component: Reports, title: 'Reports' },
  { path: 'admin', component: Admin, title: 'Admin' },
  { path: '**', redirectTo: '' }, // unknown URL -> Home
];
