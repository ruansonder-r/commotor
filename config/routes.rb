Rails.application.routes.draw do
  get "up" => "rails/health#show", as: :rails_health_check

  resource :session, only: [ :new, :create, :destroy ]

  get "dashboard", to: "dashboard#index", as: :dashboard

  resources :carpool_groups, only: [ :show ] do
    resources :trip_logs, only: [ :create ]
    resource :receipt, only: [ :show ]
  end

  namespace :admin do
    root "cars#index"
    resources :cars
    resources :trips
    resources :carpool_groups
    resources :memberships
    resources :users, only: [ :index ]
  end

  root "dashboard#index"
end
