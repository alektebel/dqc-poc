import { Component, inject } from '@angular/core';
import { Router, RouterLink } from '@angular/router';

@Component({
  imports: [RouterLink],
  selector: 'app-reports',
  styleUrl: './reports.css',
  templateUrl: './reports.html',
})
export class Reports {
  protected readonly router = inject(Router);

  protected readonly links = [
    { path: '/', label: 'Back to Home' },
    { path: '/orders', label: 'Go to Orders' },
    { path: '/admin', label: 'Go to Admin' },
  ];

  go(path: string) {
    this.router.navigate([path]);
  }
}
