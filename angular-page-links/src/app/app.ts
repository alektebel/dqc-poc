import { Component } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

@Component({
  // RouterOutlet renders the active page; RouterLink/RouterLinkActive power the nav.
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  selector: 'app-root',
  styleUrl: './app.css',
  templateUrl: './app.html',
})
export class App {
  // One entry per page. Add a page here and it shows up in the top nav too.
  protected readonly pages = [
    { path: '/', label: 'Home' },
    { path: '/orders', label: 'Orders' },
    { path: '/reports', label: 'Reports' },
    { path: '/admin', label: 'Admin' },
  ];
}
