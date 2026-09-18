import { Component, inject } from '@angular/core';
import { Router, RouterLink } from '@angular/router';

@Component({
  imports: [RouterLink],
  selector: 'app-orders',
  styleUrl: './orders.css',
  templateUrl: './orders.html',
})
export class Orders {
  protected readonly router = inject(Router);

  protected readonly links = [
    { path: '/', label: 'Back to Home' },
    { path: '/reports', label: 'Go to Reports' },
    { path: '/admin', label: 'Go to Admin' },
  ];

  go(path: string) {
    this.router.navigate([path]);
  }
}
