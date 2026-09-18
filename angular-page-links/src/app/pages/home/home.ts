import { Component, inject } from '@angular/core';
import { Router, RouterLink } from '@angular/router';

@Component({
  imports: [RouterLink],
  selector: 'app-home',
  styleUrl: './home.css',
  templateUrl: './home.html',
})
export class Home {
  protected readonly router = inject(Router);

  // The buttons on THIS page. Change `path` to retarget a button.
  // Each path must match a route in src/app/app.routes.ts.
  protected readonly links = [
    { path: '/orders', label: 'Go to Orders' },
    { path: '/reports', label: 'Go to Reports' },
    { path: '/admin', label: 'Go to Admin' },
  ];

  // The programmatic variant: called from a (click) handler.
  go(path: string) {
    this.router.navigate([path]);
  }
}
