// 웹푸시 서비스워커. 탭/브라우저가 닫혀있어도 서버가 보낸 push 메시지를 받아 OS 알림으로
// 띄우는 역할을 한다 - 지금 있던 Notification API(포그라운드 폴링, AlarmPage.tsx의
// checkAndFire)와 달리, 진짜 백그라운드 알림은 이 서비스워커를 거쳐야만 가능하다.

self.addEventListener("push", (event) => {
  let payload = { title: "복약 알림", body: "복약 시간이에요!" };
  try {
    if (event.data) {
      payload = event.data.json();
    }
  } catch {
    // 서버가 JSON이 아닌 형태로 보냈으면 기본 문구로 대체 - 알림 자체는 뜨게 한다.
  }

  // actions/data가 있으면(복약알림 본인 몫 - push_service.py의 intake_sources) "복용완료"/
  // "빈도 줄이기" 버튼을 붙인다. 없으면(가족에게 전달된 사본, 습관 달성 알림 등) 그냥 텍스트만.
  event.waitUntil(
    self.registration.showNotification(payload.title, {
      body: payload.body,
      actions: payload.actions,
      data: payload.data,
    }),
  );
});

// 액션 버튼(복용완료/빈도줄이기) 클릭 시 로그인 세션 없이 백엔드에 요청한다 - 서비스워커는
// 앱이 완전히 꺼져있어도 실행되지만 페이지 메모리에만 있는 JWT엔 접근할 수 없다
// (app/dtos/push.py의 MarkTakenRequest/ReduceFrequencyRequest 주석 참고). 그 외(본문 클릭
// 등)는 기존대로 앱 포커스/열기만 한다.

// 같은 시각에 여러 약이 겹치면(F-NTFY-2) 알림 하나에 항목이 여러 개 묶여 온다
// (notification.data.items) - "복용완료"/"빈도 줄이기"는 묶인 항목 전체에 적용되므로
// 항목마다 요청을 반복한다. 하나가 실패해도 나머지는 계속 시도한다(Promise.allSettled).
function postForEachItem(url, items, profile_id) {
  return Promise.allSettled(
    items.map((item) =>
      fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile_id, ...item }),
      }),
    ),
  );
}

self.addEventListener("notificationclick", (event) => {
  const { action, notification } = event;
  notification.close();

  // "복용완료"(F-NTFY-1) - 이 알림에 묶인 항목 전체를 오늘 복용한 것으로 서버(F-ADH-1
  // medication_intake_logs)에 기록한다.
  if (action === "intake_complete") {
    const { profile_id, items } = notification.data || {};
    if (profile_id && items && items.length > 0) {
      // allSettled라 개별 fetch 실패는 이미 내부에서 흡수된다 - 오프라인 등으로 실패해도
      // 알림 자체는 이미 닫혔으니 별도 처리 없이 조용히 넘어간다.
      event.waitUntil(postForEachItem("/api/v1/push/mark-taken", items, profile_id));
    }
    return;
  }

  // "빈도 줄이기"(F-NTFY-3) - alarm_time까지 같이 보내야 medication_schedule의 여러 시각
  // 중 정확히 이 알림이 울린 시각만 서버가 골라 뺄 수 있다. 묶인 항목 전체에 적용된다.
  if (action === "reduce_freq") {
    const { profile_id, items } = notification.data || {};
    if (profile_id && items && items.length > 0) {
      event.waitUntil(postForEachItem("/api/v1/push/reduce-frequency", items, profile_id));
    }
    return;
  }

  // "불편한 증상이 있어요"(F-NTFY-5 부작용 사전 안내 전용) - data.url로 챗봇 자동질문
  // 딥링크를 받아 연다. 이미 열려있는 탭이 있으면 그 탭을 그 URL로 이동시키고, 없으면
  // 새 창을 연다(탭이 완전히 닫혀있던 경우 - clients.openWindow만 가능).
  if (action === "open_consult") {
    const { url } = notification.data || {};
    if (url) {
      event.waitUntil(
        self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientList) => {
          for (const client of clientList) {
            if ("navigate" in client && "focus" in client) {
              return client.navigate(url).then(() => client.focus());
            }
          }
          if (self.clients.openWindow) return self.clients.openWindow(url);
          return undefined;
        }),
      );
    }
    return;
  }

  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if ("focus" in client) return client.focus();
      }
      if (self.clients.openWindow) return self.clients.openWindow("/alarms");
      return undefined;
    }),
  );
});
