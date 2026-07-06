// src/routes/router.tsx
import { createBrowserRouter, Navigate } from "react-router-dom";
import Layout from "../components/ui/Layout";
import ProtectedRoute from "./ProtectedRoute";

import LoginPage from "../features/auth/LoginPage";
import SignupPage from "../features/auth/SignupPage";
import SchedulePage from "../features/schedule/SchedulePage";
import EmergencyCardPage from "../features/emergency_card/EmergencyCardPage";
import PwaSubscriptionPage from "../features/pwa_subscription/PwaSubscriptionPage";
import SupportGroupPage from "../features/support_group/SupportGroupPage";
import RecordPage from "../features/record/RecordPage";
import MedicationPage from "../features/medication/MedicationPage";
import IntakeLogPage from "../features/intake_log/IntakeLogPage";
import FoodIntakePage from "../features/food_intake/FoodIntakePage";
import DrugFoodInteractionPage from "../features/drug_food_interaction/DrugFoodInteractionPage";
import HealthMetricPage from "../features/health_metric/HealthMetricPage";
import AppointmentPage from "../features/appointment/AppointmentPage";
import SymptomLogPage from "../features/symptom_log/SymptomLogPage";
import ChatPage from "../features/chat/ChatPage";
import GeneratedGuidePage from "../features/generated_guide/GeneratedGuidePage";

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  { path: "/signup", element: <SignupPage /> },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <Layout />,
        children: [
          { path: "/", element: <Navigate to="/schedules" replace /> },
          { path: "/schedules", element: <SchedulePage /> },
          { path: "/records", element: <RecordPage /> },
          { path: "/medications", element: <MedicationPage /> },
          { path: "/intake-logs", element: <IntakeLogPage /> },
          { path: "/food-intake", element: <FoodIntakePage /> },
          { path: "/drug-food-interactions", element: <DrugFoodInteractionPage /> },
          { path: "/health-metrics", element: <HealthMetricPage /> },
          { path: "/appointments", element: <AppointmentPage /> },
          { path: "/symptom-logs", element: <SymptomLogPage /> },
          { path: "/emergency-card", element: <EmergencyCardPage /> },
          { path: "/support-group", element: <SupportGroupPage /> },
          { path: "/pwa-subscription", element: <PwaSubscriptionPage /> },
          { path: "/chat", element: <ChatPage /> },
          { path: "/generated-guides", element: <GeneratedGuidePage /> },
        ],
      },
    ],
  },
]);
