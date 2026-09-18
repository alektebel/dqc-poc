import { Component, inject } from '@angular/core';
import { Router, RouterLink } from '@angular/router';

@Component({
  imports: [RouterLink],
  selector: 'app-admin',
  styleUrl: './admin.css',
  templateUrl: './admin.html',
})
export class Admin {
  protected readonly router = inject(Router);

  protected readonly links = [
    { path: '/', label: 'Back to Home' },
    { path: '/orders', label: 'Go to Orders' },
    { path: '/reports', label: 'Go to Reports' },
  ];

  go(path: string) {
    this.router.navigate([path]);
  }
}
